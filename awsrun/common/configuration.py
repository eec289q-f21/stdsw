import os
import pathlib
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum

import objectfactory

from aws import S3Handler, SqsHandler, subscribe, list_subscriptions, get_topic, create_or_get_topic, delete_topic, \
    create_topic, AWSBackend
from common.resources import Folder, S3Path, OSPath, Path


class AWSTags(Enum):
    REGION = 'Region'
    FILES = 'Bucket'
    TASKS = 'TaskQueue'
    REGISTRY = 'RegQueue'
    SUBSCRIPTION = 'Notification'
    GROUPS = 'Groups'


class InfraComponent(ABC):
    handler = property(fget=lambda self: self._handler())
    component = property(fget=lambda self: self._aws_component())

    def __init__(self, server_path, name):
        self._server = server_path
        self._name = name

    @abstractmethod
    def build(self, **kwargs):
        pass

    @abstractmethod
    def destroy(self):
        pass

    @abstractmethod
    def get_arn(self):
        pass

    @abstractmethod
    def _handler(self):
        pass

    @abstractmethod
    def _aws_component(self):
        pass

    def report(self, tag):
        return {tag: (self._name,)}

    @property
    def name(self):
        return self._name

    @property
    def path(self):
        return self._server

    @staticmethod
    def _new(tag, *args):
        if tag == AWSTags.REGION:
            return AWSInfra(*args)
        elif tag == AWSTags.FILES:
            return S3Component(*args)
        elif tag == AWSTags.TASKS:
            return QueueComponent(*args)
        elif tag == AWSTags.REGISTRY:
            return QueueComponent(*args)
        elif tag == AWSTags.SUBSCRIPTION:
            return SubscriptionComponent(*args)
        else:
            raise RuntimeError("unknown tag")

    @staticmethod
    def new(tag, region, *args):
        return InfraComponent._new(tag, region, *args)


class S3Component(InfraComponent):
    def __init__(self, server_path, bucket_name):
        super().__init__(server_path, bucket_name)

    def build(self, **kwargs):
        handler: S3Handler = self.handler
        if not handler.bucket_exists(self.name):
            handler.create_bucket(self.name)

    def destroy(self):
        handler = self.handler
        if handler.bucket_exists(self._name):
            handler.delete_bucket(self.component)

    def get_arn(self):
        return S3Handler.get_bucket_arn(self.name)

    def _handler(self):
        return S3Handler(self._server)

    def _aws_component(self):
        return self.handler.get_bucket(self._name)


class QueueComponent(InfraComponent):
    def __init__(self, server_path, queue_name):
        super().__init__(server_path, queue_name)
        self._name = queue_name

    def build(self, **kwargs):
        handler: SqsHandler = self.handler
        if not handler.queue_exists(self._name):
            handler.create_queue(self._name)

    def destroy(self):
        if self.handler.queue_exists(self._name):
            self.handler.remove_queue(self.component)

    def get_arn(self):
        return self.component.attributes["QueueArn"]

    def _handler(self):
        return SqsHandler(self._server)

    def _aws_component(self):
        return self.handler.get_queue(self._name)


class SubsHandler:
    def __init__(self, topic, domains):
        self._pattern = domains
        self._topic = topic

    def new(self, email_txt):
        all_emails = re.findall(r'[\w\.-]+@[\w\.-]+', email_txt)
        for email in all_emails:
            domain = re.findall('@+\S+[.edu|.com]', email)[0]
            if domain in self._pattern:
                return subscribe(self._topic, 'email', email)
        return None

    def confirmed_emails(self):
        all_subscriptions = list_subscriptions(self._topic)
        authenticated_emails = list(filter(lambda sub: sub.arn != 'PendingConfirmation', all_subscriptions))
        return list(map(lambda sub: sub.attributes['Endpoint'], authenticated_emails))

    def is_confirmed(self, email):
        return email in self.confirmed_emails()


class SubscriptionComponent(InfraComponent):
    def __init__(self, server_path, name, domains):
        super().__init__(server_path, name)
        self._domains = domains
        self._sub_handler = SubsHandler(self.build() ,domains)

    def build(self, **kwargs):
        if not self.component:
            topic = create_topic(self._name)
            return topic
        return get_topic(self._name)

    def destroy(self):
        if self.component:
            delete_topic(self.component)

    def get_arn(self):
        acc_id = AWSBackend().get_account_id()
        return "arn:aws:sns:{}:{}:{}".format(self.path, acc_id, self.name)

    def report(self, tag):
        return {tag: (self._name, self._domains)}

    def _handler(self):
        return self._sub_handler

    def _aws_component(self):
        return get_topic(self._name)


class AWSInfra(InfraComponent):
    def get_arn(self):
        arn_dict = dict()
        for component in self._children:
            arn_dict[component.name] = component.get_arn()
        return arn_dict

    def _aws_component(self):
        ret = dict()
        for key, val in self._children:
            ret[key] = val.component
        return ret

    def build(self, **kwargs):
        # infra build!!!!
        self._load(**kwargs)
        component_tags = list(map(lambda t: t.value, AWSTags))
        aws_data = dict(filter(lambda i: not (i[0] in component_tags), kwargs.items()))
        for component in self._children.values():
            component.build(**aws_data)

    def destroy(self):
        for component in self._children.values():
            component.destroy()

    def __init__(self, server_path, name="InfraStructure"):
        super().__init__(server_path, name)
        self._children = dict()

    def add(self, child: InfraComponent, tag: AWSTags):
        self._children[tag] = child

    def remove(self, tag: AWSTags):
        return self._children.pop(tag)

    def get(self, tag: AWSTags):
        if tag in self._children:
            return self._children[tag]
        return None

    def has(self, tag: AWSTags):
        return tag in self._children

    def report(self, tag=None):
        if tag is None:
            tag = AWSTags.REGION.value
        rep = {tag: (self._server,)}
        for key, component in self._children.items():
            rep = {**rep, **(component.report(key.value))}

        return rep

    def _load(self, **kwargs):
        component_tags = list(map(lambda t: t.value, AWSTags))
        factory_data = filter(lambda i: i[0] in component_tags, kwargs.items())
        for key, value in factory_data:
            tag = AWSTags(key)
            component = InfraComponent.new(tag, self.path, *value)
            self.add(component, tag)
        return self

    def _handler(self):
        return self._children

    @staticmethod
    def load(data):
        region = data.pop(AWSTags.REGION.value)
        aws_infra = AWSInfra(*region)
        aws_infra._load(**data)
        return aws_infra


class AWSPathManager:
    def __init__(self, infra: AWSInfra):
        self._aws_infra = infra

    def load_url(self):
        pass

    def load_file(self):
        pass

    @property
    def server_path(self):
        return Path(self._aws_infra.path)

    @property
    def bucket_path(self):
        return Path(self._aws_infra.get(AWSTags.FILES).name)

    @property
    def taskq_path(self):
        task_queue = self._aws_infra.get(AWSTags.TASKS).component
        return Path(task_queue.url)

    @property
    def regq_path(self):
        if self._aws_infra.has(AWSTags.REGISTRY):
            reg_queue = self._aws_infra.get(AWSTags.REGISTRY).component
            return Path(reg_queue.url)
        else:
            return Path('')


@objectfactory.Factory.register_class
class WSConfig(objectfactory.Serializable):
    _wsfolder = objectfactory.Field()
    _targetprefix = objectfactory.Field()

    @staticmethod
    def new(wsfolder, tgtprefix):
        wsconfig = WSConfig()
        wsconfig._wsfolder = wsfolder
        wsconfig._targetprefix = tgtprefix
        return wsconfig

    @staticmethod
    def new(tgtprefix):
        wsconfig = WSConfig()
        wsconfig._wsfolder = WSConfig.unique_root()
        wsconfig._targetprefix = tgtprefix
        return wsconfig

    @property
    def root(self):
        return Folder(self._wsfolder)

    @property
    def local_input(self):
        return self._wsfolder + "_in.tar"

    @property
    def input(self):
        return S3Path(self.local_input, self._generate_key(self.local_input))

    @property
    def local_output(self):
        return self._wsfolder + "_out.tar"

    @property
    def output(self):
        return S3Path(self.local_output, self._generate_key(self.local_output))

    def _generate_key(self, path):
        return self._targetprefix + os.path.sep + self._wsfolder + os.path.sep + path

    @staticmethod
    def unique_root(prefix="ws"):
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        return prefix + "_" + timestamp + "_" + str(uuid.uuid4())


@objectfactory.Factory.register_class
class CmdConfig(objectfactory.Serializable):
    _command = objectfactory.Field()
    _timeout = objectfactory.Field()
    _cores = objectfactory.Field()
    _depcfg = objectfactory.Field()

    @staticmethod
    def new(cmd, timeout, cores, depfile):
        cmdconfig = CmdConfig()
        cmdconfig._command = cmd
        cmdconfig._timeout = timeout
        cmdconfig._cores = cores
        cmdconfig._depcfg = depfile
        return cmdconfig.normalize()

    @property
    def shell(self):
        return self._command

    @property
    def timeout(self):
        return self._timeout

    @property
    def cores(self):
        return self._cores

    def normalize(self):
        for i in range(len(self.shell)):
            cmd_arg = self.shell[i]
            if os.path.exists(cmd_arg) and (not os.path.isabs(cmd_arg)):
                self.shell[i] = os.path.abspath(cmd_arg)
        return self

    def relativize(self):
        for i in range(len(self.shell)):
            cmd_arg = self.shell[i]
            if cmd_arg.startswith(os.path.sep):
                self.shell[i] = "." + cmd_arg

    @property
    def deps(self):
        try:
            with open(self._depcfg, "r") as f:
                extra_files = list(f.readlines())
        except FileNotFoundError:
            return []
        else:
            cleaned_extra_files = []
            for extra_file in extra_files:
                stripped_extra_file = extra_file.strip()
                if len(stripped_extra_file) > 0:
                    for x in pathlib.Path(".").glob(stripped_extra_file):
                        cleaned_extra_files.append(OSPath.new(str(x)))
            return cleaned_extra_files

import json
from abc import ABC, abstractmethod
import objectfactory
from common.configuration import CmdConfig, WSConfig
from utils.Meta import reconcile_meta


class IMessage(ABC):
    @abstractmethod
    def flatten(self):
        pass


class AWSMsg(reconcile_meta(objectfactory.Serializable, IMessage, ABC)):
    def flatten(self):
        return json.dumps(self.serialize())


@objectfactory.Factory.register_class
class AWSIDRegistration(AWSMsg):
    _awsid = objectfactory.Field()
    _email = objectfactory.Field()

    @staticmethod
    def new( id, email):
        reg = AWSIDRegistration()
        reg._awsid = id
        reg._email = email
        return reg
    @property
    def id(self):
        return self._awsid

    @property
    def email(self):
        return self._email


@objectfactory.Factory.register_class
class IOTask(AWSMsg):
    _cmdconfig = objectfactory.Nested()
    _wsconfig = objectfactory.Nested()
    _localwd = objectfactory.Field()
    _perf_file = objectfactory.Field()

    @staticmethod
    def new(cmdconfig: CmdConfig, wsconfig: WSConfig, localwd, perf_file):
        iotask = IOTask()
        iotask._cmdconfig = cmdconfig
        iotask._wsconfig = wsconfig
        iotask._localwd = localwd
        iotask._perf_file = perf_file
        return iotask

    @property
    def command(self):
        return self._cmdconfig

    @property
    def workspace(self):
        return self._wsconfig

    @property
    def lwd(self):
        return self._localwd

    @property
    def perf_file(self):
        return self._perf_file

    @property
    def cores(self):
        return self.command.cores

    @property
    def timeout(self):
        return self._cmdconfig.timeout

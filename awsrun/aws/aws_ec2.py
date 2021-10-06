import datetime
import logging
import re
import sys
import time
from typing import Optional
from aws.aws_backend import AWSBackend
from utils.Meta import Singleton
from utils.constant import Const
from boto3_type_annotations.ec2 import Client, ServiceResource, Instance


class VPCManager:
    def __init__(self):
        self._ec2cli: Client = AWSBackend().get_client(service='ec2')
        self.logger = logging.getLogger(VPCManager.__class__.__name__)

    def _name_it(self, resource_id, name):
        return self._ec2cli.create_tags(
            Resources=[resource_id],
            Tags=[{
                "Key": "Name",
                "Value": name
            }]
        )

    def create_vpc(self, name, cidr_block="10.0.0.0/16"):
        response = self._ec2cli.create_vpc(
            CidrBlock=cidr_block
        )
        vpc_id = response["Vpc"]["VpcId"]
        self._name_it(vpc_id, name)
        self.logger.info("Created vpc %s with cidr block  %s ", name, cidr_block)
        return vpc_id

    def create_igw(self):
        response = self._ec2cli.create_internet_gateway()
        self.logger.info("created an internet gateway")
        return response["InternetGateway"]["InternetGatewayId"]

    def attach_igw2vpc(self, igw_id, vpc_id):
        self.logger.info("Attaching IGW %s to VPC %s", igw_id, vpc_id)
        return self._ec2cli.attach_internet_gateway(
            InternetGatewayId=igw_id,
            VpcId=vpc_id
        )

    def create_subnet(self, name, vpc_id, cidr_block):
        response = self._ec2cli.create_subnet(
            VpcId=vpc_id,
            CidrBlock=cidr_block
        )
        subnet_id = response["Subnet"]["SubnetId"]
        self._name_it(subnet_id, name)
        self.logger.info("Created a subnet for VPC %s with CIDR block %s", vpc_id, cidr_block)
        return subnet_id

    def create_routing_table(self, vpc_id):
        response = self._ec2cli.create_route_table(VpcId=vpc_id)
        self.logger.info("Created a routing table for VPC  %s", vpc_id)
        return response["RouteTable"]["RouteTableId"]

    def add_igw_route(self, rtb_id, igw_id, dest_cidr="0.0.0.0/0"):
        self.logger.info("adding route for igw %s to the route table %s", igw_id, rtb_id)
        return self._ec2cli.create_route(
            RouteTableId=rtb_id,
            GatewayId=igw_id,
            DestinationCidrBlock=dest_cidr
        )

    def route_subnet(self, subnet_id, rtb_id):
        self.logger.info("routing subnet %s with routing table %s", subnet_id, rtb_id)
        return self._ec2cli.associate_route_table(
            SubnetId=subnet_id,
            RouteTableId=rtb_id
        )

    def enable_auto_ip(self, subnet_id):
        self.logger.info("enabling the subnet %s for auto ip assignment", subnet_id)
        return self._ec2cli.modify_subnet_attribute(
            SubnetId=subnet_id,
            MapPublicIpOnLaunch={"Value": True}
        )


class IPPermissions:
    @staticmethod
    def ssh_access():
        return {
            "IpProtocol": "tcp",
            "FromPort": 22,
            "ToPort": 22,
            "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
        };

    @staticmethod
    def http_access():
        return {
            "IpProtocol": "tcp",
            "FromPort": 80,
            "ToPort": 80,
            "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
        };


class InstanceType:
    def __init__(self, name, cpu, ram_gb):
        self._name = name
        self._cpu = cpu
        self.ram_gb = ram_gb
        self.prices = []
        self.avg_price = 0.0
        self.max_price = 0.0
        self.calc_cost = sys.maxsize
        self.metric_cost = sys.maxsize

    def calc_avg(self):
        if sum(self.prices) > 0:
            self.avg_price = (sum(self.prices) / len(self.prices))
        else:
            self.avg_price = sys.maxsize

    def add_price(self, price):
        self.prices.append(price)
        if price > self.max_price:
            self.max_price = price

    def calculate_metric_cost(self, metric):
        if self.avg_price <= 0:
            return
        if metric == "ram":
            self.metric_cost = self.avg_price / self.ram_gb
        else:
            self.metric_cost = self.avg_price / self._cpu

    def calculate_ratio(self, ratio):
        if self.avg_price <= 0:
            return
        else:
            cpu, ram = ratio.split(':')
            num_of_cont = min((self._cpu / int(cpu)), (self.ram_gb / int(ram)))
            if num_of_cont > 0:
                self.metric_cost = self.avg_price / num_of_cont

    def to_json(self):
        return {"name": self._name, "cpu": self._cpu, "ram": self.ram_gb,
                "avg_price": self.avg_price, "max_price": self.max_price}

    @property
    def name(self):
        return self._name

    @property
    def ram(self):
        return self.ram_gb

    @property
    def cpu(self):
        return self._cpu


class T2Instances:
    @staticmethod
    def nano():
        return InstanceType("t2.nano", 1, 0.5)

    @staticmethod
    def micro():
        return InstanceType("t2.micro", 1, 1)

    @staticmethod
    def small():
        return InstanceType("t2.small", 1, 2)

    @staticmethod
    def medium():
        return InstanceType("t2.medium", 2, 4)

    @staticmethod
    def large():
        return InstanceType("t2.large", 2, 8)

    @staticmethod
    def xlarge():
        return InstanceType("t2.xlarge", 4, 16)

    @staticmethod
    def x2large():
        return InstanceType("t2.2xlarge", 8, 32)


class InstanceState(Const):
    PENDING = [0, 'pending']
    RUNNING = [16, 'running']
    SHUTTING = [32, 'shutting-down']
    TERMINATED = [48, 'terminated']
    STOPPING = [64, 'stopping']
    STOPPED = [80, 'stopped']

    @staticmethod
    def code(state):
        return state[0]

    @staticmethod
    def status(state):
        return state[1]


@Singleton
class EC2InstanceUtility:
    def __init__(self):
        self._ec2res: ServiceResource = AWSBackend().get_resource(service='ec2')
        self._ec2cli: Client = AWSBackend().get_client(service='ec2')

    def _get_instance_state(self, inst_id):
        for instance in self._ec2res.instances.all():
            if instance.id == inst_id:
                return instance.state['Name']
        return InstanceState.status(InstanceState.PENDING)

    def get_instance_statuses(self, inst_ids, max_retry=1):
        response = self._ec2cli.describe_instance_status(
            InstanceIds=inst_ids
        )
        while not response['InstanceStatuses'] and max_retry > 0:
            response = self._ec2cli.describe_instance_status(
                InstanceIds=inst_ids
            )
            max_retry -= 1
        return response['InstanceStatuses']

    def get_instance_by_id(self,id):
        return self.get_instances_by_id([id])[0]

    def get_instances_by_id(self,ids):
        return list(self._ec2res.instances.filter(InstanceIds=ids))

    # running vs stopped
    def get_instance_status(self, inst_id, max_retry=5, default=None):
        instances = self.get_instance_statuses([inst_id], max_retry=max_retry)
        if not instances:
            if default:
                return default
            else:
                return self._get_instance_state(inst_id)
        else:
            return instances[0]['InstanceState']['Name']

    def get_instance_state(self, instance_id, max_retry=5):
        instances = self.get_instance_statuses([instance_id], max_retry=max_retry)
        if instances:
            for instance in instances:
                if instance['InstanceId'] == instance_id:
                    return instance['InstanceStatus']['Details'][0]['Status']
        else:
            return 'Initializing'

    @staticmethod
    def get_tag_value(instance, key):
        if instance.tags is None:
            return None
        for tag in instance.tags:
            if tag['Key'] == key:
                return tag['Value']
        return None

    @staticmethod
    def filter_instances_by_function(f, instances):
        return list(filter(f, instances))

    @staticmethod
    def filter_instances_by_tag(tag: tuple, instances):
        assert len(tag) == 2, "tag must be key/value pair"
        return EC2InstanceUtility.filter_instances_by_function(
            lambda i: False if i.tags is None else any(
                map(lambda t: t['Key'] == tag[0] and t['Value'] == tag[1], i.tags)), instances)

    @staticmethod
    def refresh_instances(instances):
        EC2InstanceUtility().get_instance_statuses(list(map(lambda i: i.id, instances)))

    @staticmethod
    def _status_check(instance, status):
        return EC2InstanceUtility().get_instance_status(instance.id) == status

    @staticmethod
    def is_ready(instance):
        return EC2InstanceUtility().get_instance_state(instance.id) == 'passed'

    @staticmethod
    def is_terminated(instance):
        return EC2InstanceUtility._status_check(instance, InstanceState.status(InstanceState.TERMINATED))

    @staticmethod
    def is_stopped(instance):
        return EC2InstanceUtility._status_check(instance, InstanceState.status(InstanceState.STOPPED))

    @staticmethod
    def is_running(instance):
        return EC2InstanceUtility._status_check(instance, InstanceState.status(InstanceState.RUNNING))

    @staticmethod
    def get_running(instances):
        return EC2InstanceUtility.filter_instances_by_function(EC2InstanceUtility.is_running, instances)

    @staticmethod
    def get_stopped(instances):
        return EC2InstanceUtility.filter_instances_by_function(EC2InstanceUtility.is_stopped, instances)

    @staticmethod
    def get_terminated(instances):
        return EC2InstanceUtility.filter_instances_by_function(EC2InstanceUtility.is_terminated, instances)

    @staticmethod
    def start_instances(instances):
        for inst in instances:
            inst.start()

    @staticmethod
    def stop_instances(instances):
        for inst in instances:
            inst.stop()

    @staticmethod
    def terminate_instances(instances):
        for inst in instances:
            if not EC2InstanceUtility.is_terminated(inst):
                inst.terminate()

    @staticmethod
    def wait_for_state(state_cb, instances, max_retry=5, interval=12, success_msg=None):
        if success_msg is None:
            success_msg = "Instances are ready as you like"
        retries = max_retry
        while retries > 0:
            if state_cb(instances):
                print(success_msg)
                return True
            retries -= 1
            print("Waiting for desired state... (retries remaining: {})".format(retries))
            time.sleep(interval)

        print("Retries exceeded. Proceeding anyway.")
        return False

    @staticmethod
    def check_expired(instance, tag_datetime, max_time):
        if EC2InstanceUtility.is_terminated(instance):
            return False
        if EC2InstanceUtility.is_stopped(instance):
            return True
        # launch time
        lt_datetime = instance.launch_time
        # localize
        tag_datetime = datetime.datetime.utc.localize(tag_datetime)
        # most recent
        recent_time = max(lt_datetime, tag_datetime)
        # delta_time
        delta = datetime.datetime.utc.localize(datetime.datetime.now()) - recent_time
        uptime = delta.total_seconds()
        return uptime > max_time


class EC2Launcher:
    def __init__(self, type_tag):
        self._ec2res: ServiceResource = AWSBackend().get_resource(service='ec2')
        self._ec2cli: Client = AWSBackend().get_client(service='ec2')
        self._type_tag = type_tag
        self._logger = logging.getLogger(EC2Launcher.__class__.__name__)

    def launch_instance(self, key_name, sg_id, subnet_id, img_id, instance_type: InstanceType, num_inst, userdata=''):
        instances = self._ec2res.create_instances(
            ImageId=img_id,
            MinCount=num_inst,
            MaxCount=num_inst,
            InstanceType=instance_type.name,
            SecurityGroupIds=[sg_id],
            SubnetId=subnet_id,
            KeyName=key_name,
            UserData=userdata
        )

        for inst in instances:
            self.tag_instance(inst.id, self._type_tag)

        return instances

    def get_ami(self, template_name):
        images = self._ec2cli.describe_images(Owners=['self'])['Images']
        chosen_image = (None, -1)
        for image in images:
            if re.match(template_name, image['Name']):
                tmp_ver = int((re.search(r'\.\d+', image['Name'])).group(0).split('.')[1])
                if tmp_ver > chosen_image[1]:
                    chosen_image = (image, tmp_ver)

        if chosen_image[1] == -1:
            raise KeyError('AMI with name "' + template_name + '" not found')
        else:
            return chosen_image

    def tag_instance(self, inst_id, *tags: tuple):
        assert all(map(lambda t: len(t) == 2, tags)), "all pairs should key/value pairs"
        self._ec2res.create_tags(Resources=[inst_id],
                                 Tags=[{'Key': tup[0], 'Value': tup[1]} for tup in tags])

    def get_instances(self, inst_ids):
        return list(self._ec2res.instances.filter(InstanceIds=inst_ids))

    def get_instance(self, inst_id) -> Optional[Instance]:
        insts = self.get_instances([inst_id])
        if insts:
            return insts[0]
        else:
            return None

    def enable_api_termination(self, inst_id):
        return self._ec2cli.modify_instance_attribute(
            InstanceId=inst_id,
            DisableApiTermination={"Value": False}
        )

    def all_instances(self):
        all_instances = list(self._ec2res.instances.all())
        return EC2InstanceUtility.filter_instances_by_tag(self._type_tag, all_instances)

    def terminate_instances(self):
        return EC2InstanceUtility.terminate_instances(self.all_instances())

    def refresh_instances(self):
        return EC2InstanceUtility.refresh_instances(self.all_instances())

    def get_running_instances(self):
        return EC2InstanceUtility.get_running(self.all_instances())

    def get_stopped_instances(self):
        return EC2InstanceUtility.get_stopped(self.all_instances())

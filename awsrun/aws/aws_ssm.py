import logging
from boto3_type_annotations.ssm import Client
from botocore.exceptions import ClientError
from aws import AWSBackend


class SSMHandler:
    def __init__(self, timeout=60):
        self._ssm_client: Client = AWSBackend().get_client('ssm')
        self._timeout = timeout
        self._logger = logging.getLogger(SSMHandler.__class__.__name__)

    def list_cmds(self, cmd_id):
        response = self._ssm_client.list_commands(CommandId=cmd_id)
        return response['Commands']

    def instance_information(self):
        return self._ssm_client.describe_instance_information()['InstanceInformationList']

    def session_output(self, cmd_id, inst_id):
        """Checks the status of a command on an instance
        """
        try:
            result = self._ssm_client.get_command_invocation(
                CommandId=cmd_id,
                InstanceId=inst_id,
            )
            return result
        except self._ssm_client.exceptions.InvocationDoesNotExist:
            return None

    def cmd_stdout(self, cmd_id, inst_id):
        """Checks the status of a command on an instance
        """
        try:
            result = self._ssm_client.get_command_invocation(
                CommandId=cmd_id,
                InstanceId=inst_id,
            )
            return result['StandardOutputContent']
        except self._ssm_client.exceptions.InvocationDoesNotExist:
            return None

    def cmd_status(self, cmd_id, inst_id):
        """Checks the status of a command on an instance
        """
        try:
            result = self._ssm_client.get_command_invocation(
                CommandId=cmd_id,
                InstanceId=inst_id
            )
            return result['Status']
        except self._ssm_client.exceptions.InvocationDoesNotExist:
            return "Failed"

    def run_cmd_on_inst(self, cmd_list, inst_id):
        """ commands = [
             'echo "hello world" > /home/ec2-user/hello.txt',  # demo comma is important!
             f'cd {repo_path}',
             'sudo git pull'
             # do stuff
         ]
         """
        try:
            response = self._ssm_client.send_command(
                InstanceIds=[inst_id],
                DocumentName='AWS-RunShellScript',
                Parameters={'commands': cmd_list},
                TimeoutSeconds=self._timeout
            )

            #cmd_id = response["Command"]["CommandId"]
            #return cmd_id
            return response
        except ClientError as e:
            self._logger.error("Unable to query SSM for {} : {}".format(inst_id, str(e)))
            if "InvalidInstanceId" in str(e):
                self._logger.error(
                    "Instance is not in Running state or SSM daemon is not running. This instance is probably still "
                    "starting up ...")
            return None

    @staticmethod
    def get_cmd_id(response):
       return response["Command"]["CommandId"]

    @staticmethod
    def get_instance_ids(response):
        return response["Command"]["InstanceIds"]
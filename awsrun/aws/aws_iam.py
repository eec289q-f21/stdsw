import itertools
import json

import botocore
from boto3_type_annotations.iam import ServiceResource, Client
from botocore.exceptions import ClientError

from aws.aws_backend import AWSBackend
from utils.Meta import Singleton


class AccessKey:
    __slots__ = (
        "access_key_id",
        "create_date",
        "secret_access_key",
        "status",
        "user_name",
    )

    def __init__(self, **kw):
        self.access_key_id = kw.get("AccessKeyId")
        self.create_date = kw.get("CreateDate")
        self.secret_access_key = kw.get("SecretAccessKey", "")
        self.status = kw.get("Status")
        self.user_name = kw.get("UserName")


@Singleton
class IAMHandler:
    def __init__(self):
        self._client: Client = AWSBackend().get_client('iam')
        self._resource: ServiceResource = AWSBackend().get_resource('iam')

    @property
    def exceptions(self):
        return self._client.exceptions

    #######################################################################################
    # USER RELATED FUNCTIONALITY!!!
    #######################################################################################
    def current_user(self):
        return self._resource.CurrentUser()

    def current_user_arn(self):
        return self.current_user().arn

    def list_user_tags(self, username):
        return self._client.list_user_tags(UserName=username)['Tags']

    def add_user2group(self, username, group_name):
        self._client.add_user_to_group(
            GroupName=group_name,
            UserName=username
        )

    def get_login_profile(self, username):
        return self._resource.LoginProfile(username)

    def create_login_profile(self, username, password):
        return self._resource.LoginProfile(username).create(Password=password, PasswordResetRequired=True)

    def create_access_key(self, username):
        try:
            response = self._client.create_access_key(UserName=username)
        except ClientError as e:
            print("%s: Error creating AccessKey" % username)
            raise
        if response:
            return response['AccessKey']['AccessKeyId'], response['AccessKey']['SecretAccessKey']

    def create_user(self, username, tags):
        return self._client.create_user(UserName=username, Tags=tags)

    def get_user(self, username):
        return self._client.get_user(UserName=username)

    def user_exists(self, username):
        try:
            self.get_user(username)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchEntity':
                return False
            else:
                self.logger.error("Unexpected error from IAM get_user:", e)
                raise
        except Exception as e:
            self.logger.error("Unexpected error from IAM get_user:", e)
            raise
        return True

    def delete_user(self, username):
        self.delete_access_keys(username)
        try:
            self._client.delete_user(UserName=username)
        except self._client.exceptions.NoSuchEntityException:
            pass

    def list_access_keys(self, username):
        iter = map(lambda r: r['AccessKeyMetadata'],
                    self._client.get_paginator('list_access_keys').paginate(UserName=username))
        chunk = itertools.chain(*iter)
        return [AccessKey(**key) for key in chunk]

    def delete_access_keys(self, username):
        try:
            keys = self.list_access_keys(username)
            for key in keys:
                self._client.delete_access_key(AccessKeyId=key.access_key_id, UserName=username)
        except self._client.exceptions.NoSuchEntityException:
            pass

    def list_users(self):
        return self._client.list_users()

    #######################################################################################
    # GROUP RELATED FUNCTIONALITY!!!
    #######################################################################################
    def create_group(self, group_name):
        return self._client.create_group(GroupName=group_name)

    def list_groups(self):
        return self._client.list_groups()

    def group_exists(self, group_name):
        group_list = self.list_groups()
        group_name_list = list(map(lambda g: g['GroupName'], group_list['Groups']))
        return group_name in group_name_list

    def delete_group(self, group_name):
        self._client.delete_group(GroupName=group_name)

    def remove_user_from_group(self, group_name, user_name):
        self._client.remove_user_from_group(GroupName=group_name, UserName=user_name)

    def get_group_arn(self, group_name):
        return self._client.get_group(GroupName=group_name)['Group']['Arn']

    #######################################################################################
    # INSTANCE RELATED FUNCTIONALITY!!!
    #######################################################################################
    def all_instance_profiles(self):
        return self._client.list_instance_profiles()

    def find_instance_profile_by_name(self, profile_name):
        response = self.all_instance_profiles()
        if response is not None:
            for inst_profile in response['InstanceProfiles']:
                if inst_profile['InstanceProfileName'] == profile_name:
                    return inst_profile
        return None

    def instance_profile(self, profile_name, path='/'):
        return self._client.create_instance_profile(InstanceProfileName=profile_name,
                                                    Path=path)

    #######################################################################################
    # POLICY BASED FUNCTIONALITY
    #######################################################################################
    def attach_policy2role(self, policy_arn, role_name):
        return self._client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn,
        )

    def create_policy(self, policyname, policy_doc):
        return self._client.create_policy(PolicyName=policyname,
                                          PolicyDocument=json.dumps(policy_doc))

    def attach_policy(self, username, policy_arn):
        return self._client.attach_user_policy(UserName=username,
                                               PolicyArn=policy_arn)

    def attach_group_policy(self, group_name, policy_arn):
        return self._client.attach_group_policy(GroupName=group_name,
                                                PolicyArn=policy_arn)

    def group_policy_exists(self, group, policy_name):
        try:
            response = self._client.get_group_policy(GroupName=group,
                                                     policy_name=policy_name)
            return True
        except Exception as e:
            return False

    def policy_exists(self, policy_arn):
        try:
            response = self._client.get_policy(PolicyArn=policy_arn)
            return True
        except Exception as e:
            return False

    def get_policy(self, policy_arn):
        return self._client.get_policy(PolicyArn=policy_arn)

    #######################################################################################
    # ROLE BASED FUNCTIONALITY
    #######################################################################################
    def create_role(self, role_name, role_policy, description=""):
        return self._client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=role_policy,
            Description=description,
        )

    def has_role_for_profile(self, profile_name, role_name):
        profile = self.find_instance_profile_by_name(profile_name)
        if profile:
            roles = profile['Roles']
            for role in roles:
                if role['RoleName'] == role_name:
                    return True

        return False

    def get_role(self, role_name):
        try:
            role = self._client.get_role(RoleName=role_name)
            return role
        except self._client.exceptions.NoSuchEntityException as e:
            return None

    def get_role_policy(self, role_name, policy_name):
        try:
            role_policy = self._client.get_role_policy(RoleName=role_name,
                                                       PolicyName=policy_name)
            return role_policy
        except self._client.exceptions.NoSuchEntityException as e:
            return None

    def role_for_instance_profile(self, profile_name, role_name):
        self._client.add_role_to_instance_profile(InstanceProfileName=profile_name,
                                                  RoleName=role_name)

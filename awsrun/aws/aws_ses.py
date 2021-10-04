from aws import AWSBackend
from boto3_type_annotations.ses import Client


class AWSSESHandler:
    def __init__(self):
        region = AWSBackend().get_available_regions('ses', closest=True)[0]
        self._client: Client = AWSBackend().get_client('ses', region=region)
        self._acc_id = AWSBackend().get_client('sts').get_caller_identity()['Account']

    def update_template(self, template):
        self._client.update_template(Template=template)

    def create_template(self, template):
        self._client.create_template(Template=template)

    def template_exists(self, template_name):
        try:
            self._client.get_template(TemplateName=template_name)
            return True
        except:
            return False

    def send_templated_email(self, ses_template_name,
                             email_to,
                             email_bcc,
                             email_from,
                             email_replyto,
                             template_data):
        destinations = {
            'ToAddresses': [email_to]
        }

        if email_bcc:
            destinations['BccAddresses'] = [email_bcc]

        self._client.send_templated_email(
            Source=email_from,
            Destination=destinations,
            ReplyToAddresses=[email_replyto],
            ReturnPath=email_from,
            Template=ses_template_name,
            TemplateData=template_data
        )

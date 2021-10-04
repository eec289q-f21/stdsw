import logging
import sys

import boto3
from botocore.config import Config
from utils.Meta import Singleton
import requests


@Singleton
class AWSBackend:
    GEOGRAPHY = {"A1": "us-east-1", "A2": "us-east-1", "AD": "eu-west-1", "AE": "ap-southeast-1",
                 "AF": "ap-southeast-1", "AG": "us-east-1", "AI": "us-east-1", "AL": "eu-west-1",
                 "AM": "eu-west-1", "AN": "us-east-1", "AO": "eu-west-1", "AP": "ap-northeast-1",
                 "AQ": "ap-southeast-2", "AR": "sa-east-1", "AS": "ap-southeast-2", "AT": "eu-west-1",
                 "AU": "ap-southeast-2", "AW": "us-east-1", "AX": "eu-west-1", "AZ": "eu-west-1",
                 "BA": "eu-west-1", "BB": "us-east-1", "BD": "ap-southeast-1", "BE": "eu-west-1",
                 "BF": "eu-west-1", "BG": "eu-west-1", "BH": "eu-west-1", "BI": "eu-west-1", "BJ": "eu-west-1",
                 "BM": "us-east-1", "BN": "ap-southeast-1", "BO": "sa-east-1", "BR": "sa-east-1",
                 "BS": "us-east-1", "BT": "ap-southeast-1", "BV": "sa-east-1", "BW": "eu-west-1",
                 "BY": "eu-west-1", "BZ": "us-east-1", "CA": "us-west-2", "CC": "ap-southeast-1",
                 "CD": "eu-west-1", "CF": "eu-west-1", "CG": "eu-west-1", "CH": "eu-west-1", "CI": "eu-west-1",
                 "CK": "ap-southeast-2", "CL": "sa-east-1", "CM": "eu-west-1", "CN": "ap-northeast-1",
                 "CO": "sa-east-1", "CR": "us-east-1", "CU": "us-east-1", "CV": "eu-west-1",
                 "CX": "ap-southeast-1", "CY": "eu-west-1", "CZ": "eu-west-1", "DE": "eu-west-1",
                 "DJ": "eu-west-1", "DK": "eu-west-1", "DM": "us-east-1", "DO": "us-east-1", "DZ": "eu-west-1",
                 "EC": "sa-east-1", "EE": "eu-west-1", "EG": "eu-west-1", "EH": "eu-west-1", "ER": "eu-west-1",
                 "ES": "eu-west-1", "ET": "eu-west-1", "EU": "eu-west-1", "FI": "eu-west-1",
                 "FJ": "ap-southeast-2", "FK": "sa-east-1", "FM": "ap-northeast-1", "FO": "eu-west-1",
                 "FR": "eu-west-1", "GA": "eu-west-1", "GB": "eu-west-1", "GD": "us-east-1", "GE": "eu-west-1",
                 "GF": "sa-east-1", "GG": "eu-west-1", "GH": "eu-west-1", "GI": "eu-west-1", "GL": "eu-west-1",
                 "GM": "eu-west-1", "GN": "eu-west-1", "GP": "us-east-1", "GQ": "eu-west-1", "GR": "eu-west-1",
                 "GS": "sa-east-1", "GT": "us-east-1", "GU": "ap-northeast-1", "GW": "eu-west-1",
                 "GY": "sa-east-1", "HK": "ap-southeast-1", "HM": "ap-southeast-2", "HN": "us-east-1",
                 "HR": "eu-west-1", "HT": "us-east-1", "HU": "eu-west-1", "ID": "ap-southeast-1",
                 "IE": "eu-west-1", "IL": "eu-west-1", "IM": "eu-west-1", "IN": "ap-southeast-1",
                 "IO": "ap-southeast-1", "IQ": "eu-west-1", "IR": "eu-west-1", "IS": "eu-west-1",
                 "IT": "eu-west-1", "JE": "eu-west-1", "JM": "us-east-1", "JO": "eu-west-1",
                 "JP": "ap-northeast-1", "KE": "eu-west-1", "KG": "ap-southeast-1", "KH": "ap-southeast-1",
                 "KI": "ap-southeast-2", "KM": "ap-southeast-1", "KN": "us-east-1", "KP": "ap-northeast-1",
                 "KR": "ap-northeast-1", "KW": "eu-west-1", "KY": "us-east-1", "KZ": "eu-west-1",
                 "LA": "ap-southeast-1", "LB": "eu-west-1", "LC": "us-east-1", "LI": "eu-west-1",
                 "LK": "ap-southeast-1", "LR": "eu-west-1", "LS": "ap-southeast-1", "LT": "eu-west-1",
                 "LU": "eu-west-1", "LV": "eu-west-1", "LY": "eu-west-1", "MA": "eu-west-1", "MC": "eu-west-1",
                 "MD": "eu-west-1", "ME": "eu-west-1", "MG": "ap-southeast-1", "MH": "ap-northeast-1",
                 "MK": "eu-west-1", "ML": "eu-west-1", "MM": "ap-southeast-1", "MN": "ap-northeast-1",
                 "MO": "ap-southeast-1", "MP": "ap-northeast-1", "MQ": "us-east-1", "MR": "eu-west-1",
                 "MS": "us-east-1", "MT": "eu-west-1", "MU": "ap-southeast-1", "MV": "ap-southeast-1",
                 "MW": "ap-southeast-1", "MX": "us-west-1", "MY": "ap-southeast-1", "MZ": "ap-southeast-1",
                 "NA": "eu-west-1", "NC": "ap-southeast-2", "NE": "eu-west-1", "NF": "ap-southeast-2",
                 "NG": "eu-west-1", "NI": "us-east-1", "NL": "eu-west-1", "NO": "eu-west-1",
                 "NP": "ap-southeast-1", "NR": "ap-southeast-2", "NU": "ap-southeast-2", "NZ": "ap-southeast-2",
                 "O1": "us-east-1", "OM": "ap-southeast-1", "PA": "us-east-1", "PE": "sa-east-1",
                 "PF": "us-west-1", "PG": "ap-southeast-2", "PH": "ap-southeast-1", "PK": "ap-southeast-1",
                 "PL": "eu-west-1", "PM": "us-east-1", "PN": "us-west-1", "PR": "us-east-1", "PS": "eu-west-1",
                 "PT": "eu-west-1", "PW": "ap-northeast-1", "PY": "sa-east-1", "QA": "eu-west-1",
                 "RE": "ap-southeast-1", "RO": "eu-west-1", "RS": "eu-west-1", "RU": "ap-northeast-1",
                 "RW": "eu-west-1", "SA": "eu-west-1", "SB": "ap-southeast-2", "SC": "ap-southeast-1",
                 "SD": "eu-west-1", "SE": "eu-west-1", "SG": "ap-southeast-1", "SH": "sa-east-1",
                 "SI": "eu-west-1", "SJ": "eu-west-1", "SK": "eu-west-1", "SL": "eu-west-1", "SM": "eu-west-1",
                 "SN": "eu-west-1", "SO": "ap-southeast-1", "SR": "sa-east-1", "ST": "eu-west-1",
                 "SV": "us-east-1", "SY": "eu-west-1", "SZ": "ap-southeast-1", "TC": "us-east-1",
                 "TD": "eu-west-1", "TF": "ap-southeast-1", "TG": "eu-west-1", "TH": "ap-southeast-1",
                 "TJ": "ap-southeast-1", "TK": "ap-southeast-2", "TL": "ap-southeast-1", "TM": "eu-west-1",
                 "TN": "eu-west-1", "TO": "ap-southeast-2", "TR": "eu-west-1", "TT": "us-east-1",
                 "TV": "ap-southeast-2", "TW": "ap-northeast-1", "TZ": "ap-southeast-1", "UA": "eu-west-1",
                 "UG": "eu-west-1", "UM": "ap-northeast-1", "US": "us-east-1", "UY": "sa-east-1",
                 "UZ": "eu-west-1", "VA": "eu-west-1", "VC": "us-east-1", "VE": "sa-east-1", "VG": "us-east-1",
                 "VI": "us-east-1", "VN": "ap-southeast-1", "VU": "ap-southeast-2", "WF": "ap-southeast-2",
                 "WS": "ap-southeast-2", "YE": "ap-southeast-1", "YT": "ap-southeast-1", "ZA": "ap-southeast-1",
                 "ZM": "eu-west-1", "ZW": "eu-west-1"}

    def __init__(self):
        self._logger = logging.getLogger(AWSBackend.__class__.__name__)

    def get_available_regions(self, service: str, default='us-west-1', closest=False):
        """AWS exposes their list of regions as an API. Gather the list."""
        regions = boto3.session.Session().get_available_regions(service)
        if not regions:
            self._logger.debug(
                "The service {} does not have available regions. Returning {} as default".format(service, default)
            )
            regions = [default]
        else:
            if closest:
                info = requests.get("http://ipinfo.io/", headers={"accept": "application/json"}).json()
                region = self.GEOGRAPHY.get(info['country'], default)
                regions.remove(region)
                regions.insert(0, region)
        return regions

    def get_client(self, service: str, profile: str = None, region: str = 'us-west-1',
                   config=None) -> boto3.Session.client:
        """Get a boto3 client for a given service"""
        logging.getLogger("botocore").setLevel(logging.CRITICAL)
        session_data = {"region_name": region}
        if profile:
            session_data["profile_name"] = profile
        session = boto3.Session(**session_data)
        if region not in self.get_available_regions(service):
            self._logger.debug(f"The service {service} is not available in this region!")
            sys.exit()
        if config is None:
            config = Config(read_timeout=5, connect_timeout=5, retries={"max_attempts": 10})
        client = session.client(service, config=config)
        self._logger.debug(
            f"{client.meta.endpoint_url} in {client.meta.region_name}: boto3 client login successful"
        )
        return client

    def get_resource(self,
                     service: str, profile: str = None, region: str = "us-west-1"
                     ) -> boto3.Session.resource:
        """Get a boto3 resource for a given service"""
        logging.getLogger("botocore").setLevel(logging.CRITICAL)
        session_data = {"region_name": region}
        if profile:
            session_data["profile_name"] = profile
        session = boto3.Session(**session_data)

        resource = session.resource(service)
        return resource

    def get_account_id(self):
        return self.get_client('sts').get_caller_identity().get('Account')

#  Copyright 2021 Collate
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  http://www.apache.org/licenses/LICENSE-2.0
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""
Helper classes to model OpenMetadata Entities,
server configuration and auth.
"""
import http.client
import json
import logging
import sys
import traceback
from typing import List, Tuple

import requests
from pydantic import BaseModel

from metadata.generated.schema.entity.data.dashboard import Dashboard
from metadata.generated.schema.entity.data.database import Database
from metadata.generated.schema.entity.data.pipeline import Pipeline
from metadata.generated.schema.entity.data.table import Table, TableProfile
from metadata.generated.schema.entity.data.topic import Topic
from metadata.generated.schema.entity.services.databaseService import DatabaseService
from metadata.generated.schema.entity.tags.tagCategory import Tag
from metadata.generated.schema.metadataIngestion.workflow import (
    Auth0SSOConfig,
    CustomOidcSSOConfig,
    GoogleSSOConfig,
    OktaSSOConfig,
    OpenMetadataServerConfig,
)
from metadata.ingestion.ometa.auth_provider import AuthenticationProvider
from metadata.ingestion.ometa.client import APIError

logger = logging.getLogger(__name__)

DatabaseServiceEntities = List[DatabaseService]
DatabaseEntities = List[Database]
Tags = List[Tag]
TableProfiles = List[TableProfile]


class TableEntities(BaseModel):
    """
    Table entity pydantic model
    """

    tables: List[Table]
    total: int
    after: str = None


class TopicEntities(BaseModel):
    """
    Topic entity pydantic model
    """

    topics: List[Topic]
    total: int
    after: str = None


class DashboardEntities(BaseModel):
    """
    Dashboard entity pydantic model
    """

    dashboards: List[Dashboard]
    total: int
    after: str = None


class PipelineEntities(BaseModel):
    """
    Pipeline entity pydantic model
    """

    pipelines: List[Pipeline]
    total: int
    after: str = None


class NoOpAuthenticationProvider(AuthenticationProvider):
    """
    Extends AuthenticationProvider class

    Args:
        config (MetadataServerConfig):

    Attributes:
        config (MetadataServerConfig)
    """

    def __init__(self, config: OpenMetadataServerConfig):
        self.config = config

    @classmethod
    def create(cls, config: OpenMetadataServerConfig):
        return cls(config)

    def auth_token(self):
        pass

    def get_access_token(self):
        return ("no_token", None)


class GoogleAuthenticationProvider(AuthenticationProvider):
    """
    Google authentication implementation

    Args:
        config (MetadataServerConfig):

    Attributes:
        config (MetadataServerConfig)
    """

    def __init__(self, config: OpenMetadataServerConfig):
        self.config = config
        self.security_config: GoogleSSOConfig = self.config.securityConfig

        self.generated_auth_token = None
        self.expiry = None

    @classmethod
    def create(cls, config: OpenMetadataServerConfig):
        return cls(config)

    def auth_token(self) -> None:
        import google.auth
        import google.auth.transport.requests
        from google.oauth2 import service_account

        credentials = service_account.IDTokenCredentials.from_service_account_file(
            self.security_config.secretKey,
            target_audience=self.security_config.audience,
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        self.generated_auth_token = credentials.token
        self.expiry = credentials.expiry

    def get_access_token(self):
        self.auth_token()
        return self.generated_auth_token, self.expiry


class OktaAuthenticationProvider(AuthenticationProvider):
    """
    Prepare the Json Web Token for Okta auth
    """

    def __init__(self, config: OpenMetadataServerConfig):
        self.config = config
        self.security_config: OktaSSOConfig = self.config.securityConfig

        self.generated_auth_token = None
        self.expiry = None

    @classmethod
    def create(cls, config: OpenMetadataServerConfig):
        return cls(config)

    async def auth_token(self) -> None:
        import time
        import uuid
        from urllib.parse import quote, urlencode

        from okta.cache.okta_cache import OktaCache
        from okta.jwt import JWT, jwt
        from okta.request_executor import RequestExecutor

        try:
            my_pem, my_jwk = JWT.get_PEM_JWK(self.security_config.privateKey)
            issued_time = int(time.time())
            expiry_time = issued_time + JWT.ONE_HOUR
            generated_jwt_id = str(uuid.uuid4())
            claims = {
                "sub": self.security_config.clientId,
                "iat": issued_time,
                "exp": expiry_time,
                "iss": self.security_config.clientId,
                "aud": self.security_config.orgURL,
                "jti": generated_jwt_id,
            }
            token = jwt.encode(claims, my_jwk.to_dict(), JWT.HASH_ALGORITHM)
            config = {
                "client": {
                    "orgUrl": self.security_config.orgURL,
                    "authorizationMode": "BEARER",
                    "rateLimit": {},
                    "privateKey": self.security_config.privateKey,
                    "clientId": self.security_config.clientId,
                    "token": token,
                    "scopes": self.security_config.scopes,
                }
            }
            request_exec = RequestExecutor(
                config=config, cache=OktaCache(ttl=expiry_time, tti=issued_time)
            )
            parameters = {
                "grant_type": "client_credentials",
                "scope": " ".join(config["client"]["scopes"]),
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": token,
            }
            encoded_parameters = urlencode(parameters, quote_via=quote)
            url = f"{self.security_config.orgURL}?" + encoded_parameters
            token_request_object = await request_exec.create_request(
                "POST",
                url,
                None,
                {
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                oauth=True,
            )
            _, res_details, res_json, err = await request_exec.fire_request(
                token_request_object[0]
            )
            if err:
                raise APIError(f"{err}")
            response_dict = json.loads(res_json)
            self.generated_auth_token = response_dict.get("access_token")
            self.expiry = response_dict.get("expires_in")
        except Exception as err:
            logger.debug(traceback.print_exc())
            logger.error(err)
            sys.exit()

    def get_access_token(self):
        import asyncio

        asyncio.run(self.auth_token())
        return self.generated_auth_token, self.expiry


class Auth0AuthenticationProvider(AuthenticationProvider):
    """
    OAuth authentication implementation
    Args:
        config (MetadataServerConfig):
    Attributes:
        config (MetadataServerConfig)
    """

    def __init__(self, config: OpenMetadataServerConfig):
        self.config = config
        self.security_config: Auth0SSOConfig = self.config.securityConfig

        self.generated_auth_token = None
        self.expiry = None

    @classmethod
    def create(cls, config: OpenMetadataServerConfig):
        return cls(config)

    def auth_token(self) -> None:
        conn = http.client.HTTPSConnection(self.security_config.domain)
        payload = (
            f"grant_type=client_credentials&client_id={self.security_config.clientId}"
            f"&client_secret={self.security_config.secretKey}&audience=https://{self.security_config.domain}/api/v2/"
        )
        headers = {"content-type": "application/x-www-form-urlencoded"}
        conn.request(
            "POST", f"/{self.security_config.domain}/oauth/token", payload, headers
        )
        res = conn.getresponse()
        data = res.read()
        token = json.loads(data.decode("utf-8"))
        self.generated_auth_token = token["access_token"]
        self.expiry = token["expires_in"]

    def get_access_token(self):
        self.auth_token()
        return self.generated_auth_token, self.expiry


class AzureAuthenticationProvider(AuthenticationProvider):
    """
    Prepare the Json Web Token for Azure auth
    """

    # TODO: Prepare JSON for Azure Auth
    def __init__(self, config: OpenMetadataServerConfig):
        self.config = config

        self.generated_auth_token = None
        self.expiry = None

    @classmethod
    def create(cls, config: OpenMetadataServerConfig):
        return cls(config)

    def auth_token(self) -> None:
        from msal import (
            ConfidentialClientApplication,  # pylint: disable=import-outside-toplevel
        )

        app = ConfidentialClientApplication(
            client_id=self.config.client_id,
            client_credential=self.config.secret_key,
            authority=self.config.authority,
        )
        token = app.acquire_token_for_client(scopes=self.config.scopes)
        try:
            self.generated_auth_token = token["access_token"]
            self.expiry = token["expires_in"]

        except KeyError as err:
            logger.error(f"Invalid Credentials - {err}")
            logger.debug(traceback.format_exc())
            logger.debug(traceback.print_exc())
            sys.exit(1)

    def get_access_token(self):
        self.auth_token()
        return self.generated_auth_token, self.expiry


class CustomOIDCAuthenticationProvider(AuthenticationProvider):
    """
    Custom OIDC authentication implementation

    Args:
        config (MetadataServerConfig):

    Attributes:
        config (MetadataServerConfig)
    """

    def __init__(self, config: OpenMetadataServerConfig) -> None:
        self.config = config
        self.security_config: CustomOidcSSOConfig = self.config.securityConfig

        self.generated_auth_token = None
        self.expiry = None

    @classmethod
    def create(
        cls, config: OpenMetadataServerConfig
    ) -> "CustomOIDCAuthenticationProvider":
        return cls(config)

    def auth_token(self) -> None:
        data = {
            "grant_type": "client_credentials",
            "client_id": self.security_config.clientId,
            "client_secret": self.security_config.secretKey,
        }
        response = requests.post(
            url=self.security_config.tokenEndpoint,
            data=data,
        )
        if response.ok:
            response_json = response.json()
            self.generated_auth_token = response_json["access_token"]
            self.expiry = response_json["expires_in"]
        else:
            raise APIError(
                error={"message": response.text}, http_error=response.status_code
            )

    def get_access_token(self) -> Tuple[str, int]:
        self.auth_token()
        return self.generated_auth_token, self.expiry

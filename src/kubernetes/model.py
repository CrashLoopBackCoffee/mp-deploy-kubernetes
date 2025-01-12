"""Configuration model."""

import os

import pulumi as p
import pydantic
import pydantic.alias_generators


class ConfigBaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        alias_generator=lambda s: s.replace('_', '-'),
        populate_by_name=True,
        extra='forbid',
    )


class EnvVarRef(ConfigBaseModel):
    envvar: str

    @property
    def value(self) -> p.Output[str]:
        return p.Output.secret(os.environ[self.envvar])


class ProxmoxConfig(ConfigBaseModel):
    node_name: str
    api_endpoint: pydantic.HttpUrl
    api_token: EnvVarRef
    verify_ssl: bool = True


class MicroK8sConfig(ConfigBaseModel):
    cloud_image_url: pydantic.HttpUrl = pydantic.Field(
        default=pydantic.HttpUrl(
            'https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img'
        )
    )


class ComponentConfig(ConfigBaseModel):
    proxmox: ProxmoxConfig
    microk8s: MicroK8sConfig

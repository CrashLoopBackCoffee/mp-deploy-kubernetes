"""Configuration model."""

import pydantic
import pydantic.alias_generators


class ConfigBaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        alias_generator=lambda s: s.replace('_', '-'),
        populate_by_name=True,
    )


class VirtualMachine(ConfigBaseModel):
    name: str
    vmid: int
    ssh_public_key: str


class Config(ConfigBaseModel):
    node_name: str
    kubernetes_version: str
    cloud_image: pydantic.AnyHttpUrl
    control_plane_vms: list[VirtualMachine]

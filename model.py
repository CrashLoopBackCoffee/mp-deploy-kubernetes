"""Configuration model."""

import pydantic
import pydantic.alias_generators


class ConfigBaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        alias_generator=lambda s: s.replace('_', '-'),
        populate_by_name=True,
    )


class VirtualMachineCommon(ConfigBaseModel):
    username: str
    ssh_public_key: str
    ssh_private_key: str


class VirtualMachine(ConfigBaseModel):
    name: str
    vmid: int


class Config(ConfigBaseModel):
    node_name: str
    talos_boot_image: pydantic.AnyHttpUrl
    talos_image: str
    all_vms: VirtualMachineCommon
    control_plane_vms: list[VirtualMachine]

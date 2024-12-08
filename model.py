"""Configuration model."""

import pydantic
import pydantic.alias_generators


class ConfigBaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        alias_generator=lambda s: s.replace('_', '-'),
        populate_by_name=True,
    )


class VirtualMachineModel(ConfigBaseModel):
    vmid: int


class ConfigModel(ConfigBaseModel):
    node_name: str
    talos_boot_image: pydantic.AnyHttpUrl
    talos_image: str
    control_plane_vms: list[VirtualMachineModel]

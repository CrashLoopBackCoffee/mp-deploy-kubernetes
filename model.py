"""Configuration model."""

import typing as t

import pydantic
import pydantic.alias_generators
import pydantic.functional_validators
import pydantic_core


class ConfigBaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        alias_generator=lambda s: s.replace('_', '-'),
        populate_by_name=True,
    )


class VirtualMachineRange(ConfigBaseModel):
    vmid_start: pydantic.PositiveInt
    number_of_nodes: pydantic.PositiveInt


class VmRangesOverlapError(pydantic_core.PydanticCustomError):
    """Ranges of different node ztypes overlap."""


class ConfigModel(ConfigBaseModel):
    node_name: str
    controlplane_nodes: VirtualMachineRange
    worker_nodes: VirtualMachineRange

    @pydantic.functional_validators.model_validator(mode='after')
    def validate_model(self) -> t.Self:
        cp_start = self.controlplane_nodes.vmid_start
        cp_end = self.controlplane_nodes.vmid_start + self.controlplane_nodes.number_of_nodes
        wk_start = self.worker_nodes.vmid_start
        wk_end = self.worker_nodes.vmid_start + self.worker_nodes.number_of_nodes

        if ((cp_start <= wk_start) and (cp_end >= wk_start)) or (
            (wk_start <= cp_start) and (wk_end >= cp_start)
        ):
            raise VmRangesOverlapError(
                'vmid_ranges_overlap',
                'The controlplane nodes VMID range [{cp_start}, {cp_end}] has an overlap with the work nodes VMID range [{wk_start}, {wk_end}].',
                {
                    'cp_start': cp_start,
                    'cp_end': cp_end,
                    'wk_start': wk_start,
                    'wk_end': wk_end,
                },
            )

        return self

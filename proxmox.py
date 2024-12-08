"""Proxmox helpers."""
import collections.abc as c
import functools

import pulumi
import pulumi_proxmoxve as proxmoxve

from model import VirtualMachineModel


@functools.lru_cache
def get_pve_provider() -> proxmoxve.Provider:
    # we will use PVE PROD to create DEV VMs, there is no point in using slow VM performance on PVE DEV:
    stack_proxmox_prod = pulumi.StackReference(f'{pulumi.get_organization()}/deploy-proxmox/prod')

    return proxmoxve.Provider(
        'pve-provider',
        endpoint=stack_proxmox_prod.get_output('api-endpoint'),
        api_token=stack_proxmox_prod.get_output('api-token'),
        insecure=stack_proxmox_prod.get_output('api-insecure'),
        ssh=proxmoxve.ProviderSshArgs(
            username=stack_proxmox_prod.get_output('ssh-user'),
            private_key=stack_proxmox_prod.get_output('ssh-private-key'),
        ),
    )


def download_iso(*, name: str, url: str, node_name: str) -> proxmoxve.download.File:
    return proxmoxve.download.File(
        name,
        content_type='iso',
        datastore_id='local',
        node_name=node_name,
        overwrite=False,
        url=url,
        opts=pulumi.ResourceOptions(provider=get_pve_provider()),
    )


def create_vm_from_cdrom(
    *,
    name: str,
    config: VirtualMachineModel,
    node_name: str,
    boot_image: proxmoxve.download.File,
) -> proxmoxve.vm.VirtualMachine:
    stack_name = pulumi.get_stack()

    return proxmoxve.vm.VirtualMachine(
        name,
        name=name,
        vm_id=config.vmid,
        tags=[stack_name],
        node_name=node_name,
        description='Kubernetes Master, maintained with Pulumi. Based on Talos Linux.',
        cpu=proxmoxve.vm.VirtualMachineCpuArgs(cores=2, type='host'),
        memory=proxmoxve.vm.VirtualMachineMemoryArgs(
            # unlike what the names suggest, `floating` is the minimum memory and `dediacted` the
            # potential maximum, when ballooning:
            dedicated=4096,
            floating=2048,
        ),
        cdrom=proxmoxve.vm.VirtualMachineCdromArgs(
            enabled=True,
            file_id=boot_image.id,
        ),
        disks=[
            proxmoxve.vm.VirtualMachineDiskArgs(
                interface='scsi0',
                size=16,
                discard='on',
                datastore_id='local-lvm',
                file_format='raw',
            ),
        ],
        network_devices=[proxmoxve.vm.VirtualMachineNetworkDeviceArgs(bridge='vmbr0')],
        agent=proxmoxve.vm.VirtualMachineAgentArgs(enabled=True),
        opts=pulumi.ResourceOptions(
            provider=get_pve_provider(),
            # disks and cdrom has contant diffs and lead to update errors, possibly a bug in provider:
            ignore_changes=['disks', 'cdrom'],
        ),
    )


class NetworkInterfaceNotFoundError(Exception):
    """The desired interface was not found."""


def get_vm_ipv4(vm: proxmoxve.vm.VirtualMachine) -> pulumi.Output[str]:
    def get_eth_interface_index(interface_names: c.Sequence[str]) -> int:
        for index, name in enumerate(interface_names):
            if name.startswith('en'):
                return index

        raise NetworkInterfaceNotFoundError(
            f'No ethernet interface found for VM {vm.name!r}.',
            interface_names,
        )

    eth_interface_index = vm.network_interface_names.apply(get_eth_interface_index)
    return eth_interface_index.apply(lambda index: vm.ipv4_addresses[index][0])

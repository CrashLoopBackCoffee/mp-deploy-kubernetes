"""Proxmox helpers."""
import collections.abc as c
import functools

import pulumi
import pulumi_proxmoxve as proxmoxve

from model import VirtualMachineRange


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


def download_iso(*, name: str, url: pulumi.Input[str], node_name: str) -> proxmoxve.download.File:
    return proxmoxve.download.File(
        name,
        content_type='iso',
        datastore_id='local',
        node_name=node_name,
        overwrite=False,
        url=url,
        opts=pulumi.ResourceOptions(provider=get_pve_provider(), delete_before_replace=True),
    )


def create_vm_from_cdrom(
    *,
    name: str,
    vmid: int,
    node_name: str,
    boot_image: proxmoxve.download.File,
    controlplane: bool,
) -> proxmoxve.vm.VirtualMachine:
    stack_name = pulumi.get_stack()

    if controlplane:
        disks = [
            # boot disk:
            proxmoxve.vm.VirtualMachineDiskArgs(
                interface='virtio0',
                size=16,
                discard='on',
                iothread=True,
                datastore_id='local-lvm',
                file_format='raw',
            ),
        ]
    else:
        disks = [
            # boot disk:
            proxmoxve.vm.VirtualMachineDiskArgs(
                interface='virtio0',
                size=12,
                discard='on',
                iothread=True,
                datastore_id='local-lvm',
                file_format='raw',
            ),
            # later used as PV for LVM-backed persistent volume:
            proxmoxve.vm.VirtualMachineDiskArgs(
                interface='virtio1',
                size=256,
                discard='on',
                iothread=True,
                datastore_id='local-lvm',
                file_format='raw',
            ),
        ]

    return proxmoxve.vm.VirtualMachine(
        name,
        name=name,
        vm_id=vmid,
        tags=[stack_name],
        node_name=node_name,
        description='Kubernetes node, maintained with Pulumi. Based on Talos Linux.',
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
        disks=disks,
        network_devices=[proxmoxve.vm.VirtualMachineNetworkDeviceArgs(bridge='vmbr0')],
        agent=proxmoxve.vm.VirtualMachineAgentArgs(enabled=True),
        opts=pulumi.ResourceOptions(
            provider=get_pve_provider(),
            # the disk is written to, ignore further updates:
            ignore_changes=['disks'],
            delete_before_replace=True,
        ),
    )


def create_vms_from_cdrom(
    pve_node_name: str,
    range_: VirtualMachineRange,
    vm_name: str,
    vm_boot_image: proxmoxve.download.File,
    *,
    controlplane: bool,
) -> dict[str, pulumi.Output[str]]:
    stack_name = pulumi.get_stack()
    address_by_name: dict[str, pulumi.Output[str]] = {}

    for index, vmid in enumerate(
        range(
            range_.vmid_start,
            range_.vmid_start + range_.number_of_nodes,
        )
    ):
        cp_node_name = f'k8s-{vm_name}-{index}'

        cp_node_vm = create_vm_from_cdrom(
            name=f'{cp_node_name}-vm-{stack_name}',
            vmid=vmid,
            node_name=pve_node_name,
            boot_image=vm_boot_image,
            controlplane=controlplane,
        )

        cp_node_ipv4 = get_vm_ipv4(cp_node_vm)
        address_by_name[cp_node_name] = cp_node_ipv4

    return address_by_name


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

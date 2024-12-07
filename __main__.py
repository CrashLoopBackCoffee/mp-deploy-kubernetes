"""Kubernetes stack."""

import collections.abc

import pulumi
import pulumi_proxmoxve as proxmoxve

from model import Config

pulumi_config = pulumi.Config()
config = Config.model_validate(pulumi_config.require_object('config'))

# we will use PVE PROD to create DEV VMs, there is no point in using slow VM performance on PVE DEV:
proxmox_stack_prod = pulumi.StackReference(f'{pulumi.get_organization()}/deploy-proxmox/prod')

provider = proxmoxve.Provider(
    'provider',
    endpoint=proxmox_stack_prod.get_output('api-endpoint'),
    api_token=proxmox_stack_prod.get_output('api-token'),
    insecure=proxmox_stack_prod.get_output('api-insecure'),
    ssh=proxmoxve.ProviderSshArgs(
        username=proxmox_stack_prod.get_output('ssh-user'),
        private_key=proxmox_stack_prod.get_output('ssh-private-key'),
    ),
)

stack_name = pulumi.get_stack()

vm_image = proxmoxve.download.File(
    'vm-image',
    content_type='iso',
    datastore_id='local',
    node_name=config.node_name,
    overwrite=False,
    url=str(config.vm_image),
    opts=pulumi.ResourceOptions(provider=provider),
)

master_config = config.control_plane_vms[0]
master_name = f'{master_config.name}-{stack_name}'

# serialize master config and extend with global config attributes:
master_config_dict = config.all_vms.model_dump() | master_config.model_dump()

# cloud_config = proxmoxve.storage.File(
#     'cloud-config',
#     node_name=config.node_name,
#     datastore_id='local',
#     content_type='snippets',
#     source_raw=proxmoxve.storage.FileSourceRawArgs(
#         data=jinja2.Template(
#             pathlib.Path('assets/cloud-init/cloud-config.yaml').read_text()
#         ).render(master_config_dict),
#         file_name=f'{master_name}.yaml',
#     ),
#     opts=pulumi.ResourceOptions(provider=provider, delete_before_replace=True),
# )


master_vm = proxmoxve.vm.VirtualMachine(
    master_name,
    name=master_name,
    vm_id=master_config.vmid,
    tags=[stack_name],
    node_name=config.node_name,
    description='Kubernetes Master, maintained with Pulumi.',
    cpu=proxmoxve.vm.VirtualMachineCpuArgs(cores=2, type='host'),
    memory=proxmoxve.vm.VirtualMachineMemoryArgs(
        # unlike what the names suggest, `floating` is the minimum memory and `dediacted` the
        # potential maximum, when ballooning:
        dedicated=4096,
        floating=2048,
    ),
    cdrom=proxmoxve.vm.VirtualMachineCdromArgs(
        enabled=True,
        file_id=vm_image.id,
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
        provider=provider,
        # disks and cdrom has contant diffs and lead to update errors, possibly a bug in provider:
        ignore_changes=['disks', 'cdrom'],
    ),
)


class NetworkInterfaceNotFoundError(Exception):
    """The desired interface was not found."""


def get_eth_interface_index(interface_names: collections.abc.Sequence[str]) -> int:
    for index, name in enumerate(interface_names):
        if name.startswith('en'):
            return index

    raise NetworkInterfaceNotFoundError('No ethernet interface found.', interface_names)


eth_interface_index = master_vm.network_interface_names.apply(get_eth_interface_index)
master_vm_ipv4 = eth_interface_index.apply(lambda index: master_vm.ipv4_addresses[index][0])
pulumi.export(f'{master_name}-ipv4', master_vm_ipv4)


# master_kube_config_command = command.remote.Command(
#     f'{master_name}-kube-config',
#     connection=command.remote.ConnectionArgs(
#         host=master_vm_ipv4,
#         user=config.all_vms.username,
#         private_key=config.all_vms.ssh_private_key,
#     ),
#     add_previous_output_in_env=False,
#     create='microk8s config',
#     # only log stderr and mark stdout as secret as it contains the private keys to cluster:
#     logging=command.remote.Logging.STDERR,
#     opts=pulumi.ResourceOptions(additional_secret_outputs=['stdout']),
# )

# # export to kube config with
# # p stack output --show-secrets k8s-master-0-dev-kube-config > ~/.kube/config
# pulumi.export(f'{master_name}-kube-config', master_kube_config_command.stdout)

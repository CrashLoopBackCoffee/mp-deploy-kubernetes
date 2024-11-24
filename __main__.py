"""Kubernetes stack."""

import pathlib

import jinja2
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

cloud_image = proxmoxve.download.File(
    'cloud-image',
    content_type='iso',
    datastore_id='local',
    node_name=config.node_name,
    overwrite=False,
    url=str(config.cloud_image),
    opts=pulumi.ResourceOptions(provider=provider),
)

master_config = config.control_plane_vms[0]
master_name = f'{master_config.name}-{stack_name}'

cloud_config = proxmoxve.storage.File(
    'cloud-config',
    node_name=config.node_name,
    datastore_id='local',
    content_type='snippets',
    source_raw=proxmoxve.storage.FileSourceRawArgs(
        data=jinja2.Template(
            pathlib.Path('assets/cloud-init/cloud-config.yaml').read_text()
        ).render(master_config.model_dump()),
        file_name=f'{master_name}.yaml',
    ),
    opts=pulumi.ResourceOptions(provider=provider, delete_before_replace=True),
)


master_vm = proxmoxve.vm.VirtualMachine(
    master_name,
    name=master_name,
    vm_id=master_config.vmid,
    tags=[stack_name],
    node_name=config.node_name,
    description='Kubernetes Master, maintained with Pulumi.',
    # cpu=proxmoxve.vm.VirtualMachineCpuArgs(cores=2),
    # memory=proxmoxve.vm.VirtualMachineMemoryArgs(dedicated=2048),
    cdrom=proxmoxve.vm.VirtualMachineCdromArgs(enabled=False),
    disks=[
        proxmoxve.vm.VirtualMachineDiskArgs(
            interface='virtio0',
            size=8,
            file_id=cloud_image.id,
            iothread=True,
            discard='on',
        ),
    ],
    network_devices=[proxmoxve.vm.VirtualMachineNetworkDeviceArgs(bridge='vmbr0')],
    agent=proxmoxve.vm.VirtualMachineAgentArgs(enabled=True),
    initialization=proxmoxve.vm.VirtualMachineInitializationArgs(
        ip_configs=[
            proxmoxve.vm.VirtualMachineInitializationIpConfigArgs(
                ipv4=proxmoxve.vm.VirtualMachineInitializationIpConfigIpv4Args(address='dhcp')
            )
        ],
        user_data_file_id=cloud_config.id,
    ),
    opts=pulumi.ResourceOptions(
        provider=provider,
        # disks and cdrom has contant diffs and lead to update errors, possibly a bug in provider:
        ignore_changes=['disks', 'cdrom'],
        replace_on_changes=['initialization'],
    ),
)


pulumi.export(f'{master_name}-ipv4', master_vm.ipv4_addresses[1][0])

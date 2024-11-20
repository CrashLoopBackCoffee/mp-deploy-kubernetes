"""Kubernetes stack."""

import pathlib

import pulumi
import pulumi_proxmoxve as proxmoxve

config = pulumi.Config()

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

pve_config = config.require_secret_object('pve')
node_name = pve_config['node-name']
stack_name = pulumi.get_stack()

cloud_image = proxmoxve.download.File(
    'cloud-image',
    content_type='iso',
    datastore_id='local',
    node_name=node_name,
    overwrite=False,
    url=config.require('cloud-image'),
    opts=pulumi.ResourceOptions(provider=provider),
)

master_config = config.require_object('master-0')
master_name = f'k8s-master-{stack_name}-0'


cloud_config = proxmoxve.storage.File(
    'cloud_config',
    node_name=node_name,
    datastore_id='local',
    content_type='snippets',
    source_raw=proxmoxve.storage.FileSourceRawArgs(
        data=pathlib.Path('assets/cloud-init/cloud-config.yaml').read_text(),
        file_name=f'{master_name}.yaml',
    ),
    opts=pulumi.ResourceOptions(provider=provider, delete_before_replace=True),
)


master_vm = proxmoxve.vm.VirtualMachine(
    master_name,
    name=master_name,
    vm_id=master_config['vmid'],
    tags=[stack_name],
    node_name=node_name,
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
        # user_account=proxmoxve.vm.VirtualMachineInitializationUserAccountArgs(
        #     username='root',
        #     password='holladiewaldfee',
        # ),
        user_data_file_id=cloud_config.id,
    ),
    opts=pulumi.ResourceOptions(
        provider=provider,
        # disks and cdrom has contant diffs and lead to update errors, possibly a bug in provider:
        ignore_changes=['disks', 'cdrom'],
        replace_on_changes=['initialization'],
    ),
)


# pulumi.export('vm IPs', master_vm.ipv4_addresses)

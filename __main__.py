"""Kubernetes stack."""

import pulumi
import pulumi_proxmoxve

config = pulumi.Config()

# we will use PVE PROD to create DEV VMs, there is no point in using slow VM performance on PVE DEV:
proxmox_stack_prod = pulumi.StackReference(f'{pulumi.get_organization()}/deploy-proxmox/prod')

provider = pulumi_proxmoxve.Provider(
    'provider',
    endpoint=proxmox_stack_prod.get_output('api-endpoint'),
    api_token=proxmox_stack_prod.get_output('api-token'),
    insecure=proxmox_stack_prod.get_output('api-insecure'),
    ssh=pulumi_proxmoxve.ProviderSshArgs(
        username=proxmox_stack_prod.get_output('ssh-user'),
        private_key=proxmox_stack_prod.get_output('ssh-private-key'),
    ),
)

pve_config = config.require_secret_object('pve')
node_name = pve_config['node-name']
stack_name = pulumi.get_stack()

cloud_image = pulumi_proxmoxve.download.File(
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

master_vm = pulumi_proxmoxve.vm.VirtualMachine(
    master_name,
    name=master_name,
    vm_id=master_config['vmid'],
    tags=[stack_name],
    node_name=node_name,
    description='Kubernetes Master, maintained with Pulumi.',
    # cpu=pulumi_proxmoxve.vm.VirtualMachineCpuArgs(cores=2),
    # memory=pulumi_proxmoxve.vm.VirtualMachineMemoryArgs(dedicated=2048),
    cdrom=pulumi_proxmoxve.vm.VirtualMachineCdromArgs(enabled=False),
    disks=[
        pulumi_proxmoxve.vm.VirtualMachineDiskArgs(
            interface='virtio0',
            size=8,
            file_id=cloud_image.id,
            iothread=True,
            discard='on',
        ),
    ],
    network_devices=[pulumi_proxmoxve.vm.VirtualMachineNetworkDeviceArgs(bridge='vmbr0')],
    # cannot be activated before qemu agent is installed agent=pulumi_proxmoxve.vm.VirtualMachineAgentArgs(enabled=True),
    initialization=pulumi_proxmoxve.vm.VirtualMachineInitializationArgs(
        ip_configs=[
            pulumi_proxmoxve.vm.VirtualMachineInitializationIpConfigArgs(
                ipv4=pulumi_proxmoxve.vm.VirtualMachineInitializationIpConfigIpv4Args(
                    address='dhcp'
                )
            )
        ],
        user_account=pulumi_proxmoxve.vm.VirtualMachineInitializationUserAccountArgs(
            username='root',
            password='holladiewaldfee',
        ),
    ),
    opts=pulumi.ResourceOptions(
        provider=provider,
        # disks and cdrom has contant diffs and lead to update errors, possibly a bug in provider:
        ignore_changes=['disks', 'cdrom'],
    ),
)


# pulumi.export('vm IPs', master_vm.ipv4_addresses)

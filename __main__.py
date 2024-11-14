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


# master_vm = pulumi_proxmoxve.vm.VirtualMachine(
#     f'k8s-master-0-{stack_name}',
#     node_name=node_name,
#     description='Kubernetes Master, maintained with Pulumi.',
#     cpu=pulumi_proxmoxve.vm.VirtualMachineCpuArgs(cores=2),
#     memory=pulumi_proxmoxve.vm.VirtualMachineMemoryArgs(dedicated=2048),
#     disks=[
#         pulumi_proxmoxve.vm.VirtualMachineDiskArgs(interface='scsi0', size=8, file_format='raw'),
#     ],
#     cdrom=pulumi_proxmoxve.vm.VirtualMachineCdromArgs(
#         enabled=True, file_id='local:iso/ubuntu-24.04.1-live-server-amd64.iso'
#     ),
#     network_devices=[pulumi_proxmoxve.vm.VirtualMachineNetworkDeviceArgs(bridge='vmbr0')],
#     opts=pulumi.ResourceOptions(provider=provider),
# )

# pulumi.export('vm IPs', master_vm.ipv4_addresses)

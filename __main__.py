"""Kubernetes stack."""

import pulumi as p
import pulumi_proxmoxve as proxmoxve

from kubernetes.microk8s import create_microk8s
from kubernetes.model import ComponentConfig

component_config = ComponentConfig.model_validate(p.Config().require_object('config'))

proxmox_provider = proxmoxve.Provider(
    'provider',
    endpoint=str(component_config.proxmox.api_endpoint),
    api_token=component_config.proxmox.api_token.value,
    insecure=not component_config.proxmox.verify_ssl,
    ssh={
        'username': 'root',
        'agent': True,
    },
)

create_microk8s(component_config, proxmox_provider)


# master_config = config.control_plane_vms[0]
# master_name = f'{master_config.name}-{stack_name}'

# # serialize master config and extend with global config attributes:
# master_config_dict = config.all_vms.model_dump() | master_config.model_dump()

# cloud_config = proxmoxve.storage.File(
#     'cloud-config',
#     node_name=config.node_name,
#     datastore_id='local',
#     content_type='snippets',
#     source_raw={
#         'data': jinja2.Template(
#             pathlib.Path('assets/cloud-init/cloud-config.yaml').read_text()
#         ).render(master_config_dict),
#         'file_name': f'{master_name}.yaml',
#     },
#     opts=pulumi.ResourceOptions(provider=provider, delete_before_replace=True),
# )


# master_vm = proxmoxve.vm.VirtualMachine(
#     master_name,
#     name=master_name,
#     vm_id=master_config.vmid,
#     tags=[stack_name],
#     node_name=config.node_name,
#     description='Kubernetes Master, maintained with Pulumi.',
#     cpu={
#         'cores': 2,
#         # use exact CPU flags of host, as migration of VM for k8s nodes is irrelevant:
#         'type': 'host',
#     },
#     memory={
#         'dedicated': 4096,  # maximum
#         'floating': 2048,  # minimum
#     },
#     cdrom={'enabled': False},
#     disks=[
#         {
#             'interface': 'virtio0',
#             'size': 8,
#             'file_id': cloud_image.id,
#             'iothread': True,
#             'discard': 'on',
#             'file_format': 'raw',
#             # hack to avoid diff in subsequent runs:
#             'speed': {
#                 'read': 10000,
#             },
#         },
#     ],
#     network_devices=[
#         {
#             'bridge': 'vmbr0',
#             'model': 'virtio',
#         }
#     ],
#     agent={'enabled': True},
#     initialization={
#         # TODO Turn into state IP address and setup DNS when config is refactored.
#         'ip_configs': [{'ipv4': {'address': 'dhcp'}}],
#         'user_data_file_id': cloud_config.id,
#     },
#     stop_on_destroy=True,
#     on_boot=stack_name == 'prod',
#     machine='q35',
#     # Linux 2.6+:
#     operating_system={'type': 'l26'},
#     opts=pulumi.ResourceOptions(
#         provider=provider,
#         # disks and cdrom has contant diffs and lead to update errors, possibly a bug in provider:
#         ignore_changes=['cdrom'],
#     ),
# )

# master_vm_ipv4 = master_vm.ipv4_addresses[1][0]
# pulumi.export(f'{master_name}-ipv4', master_vm_ipv4)

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

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

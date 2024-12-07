"""Kubernetes stack."""

import collections.abc
import json
import typing as t

import pulumi
import pulumi_proxmoxve as proxmoxve
import pulumiverse_talos as talos

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
    url=str(config.talos_boot_image),
    opts=pulumi.ResourceOptions(provider=provider),
)

master_config = config.control_plane_vms[0]
master_name = f'{master_config.name}-{stack_name}'

# serialize master config and extend with global config attributes:
master_config_dict = config.all_vms.model_dump() | master_config.model_dump()

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

cluster_endpoint = pulumi.Output.concat('https://', master_vm_ipv4, ':6443')
pulumi.export(f'cluster-endpoint-{stack_name}', cluster_endpoint)

secrets = talos.machine.Secrets(f'{master_name}-talos-secrets')

cluster_name = f'common-{stack_name}'

configuration = talos.machine.get_configuration_output(
    cluster_name=cluster_name,
    machine_type='controlplane',
    cluster_endpoint=cluster_endpoint,
    # resolve nested outputs, see https://github.com/pulumiverse/pulumi-talos/issues/93:
    machine_secrets=talos.machine.MachineSecretsArgs(
        certs=secrets.machine_secrets.certs,
        cluster=secrets.machine_secrets.cluster,
        secrets=secrets.machine_secrets.secrets,
        trustdinfo=secrets.machine_secrets.trustdinfo,
    ),
    config_patches=[
        json.dumps(
            {
                'machine': {
                    'install': {
                        'image': config.talos_image,
                    }
                }
            }
        )
    ],
)

configuration_apply = talos.machine.ConfigurationApply(
    f'{master_name}-talos-configuration-apply',
    # resolve nested outputs, see https://github.com/pulumiverse/pulumi-talos/issues/93:
    client_configuration=talos.machine.ClientConfigurationArgs(
        ca_certificate=secrets.client_configuration.ca_certificate,
        client_certificate=secrets.client_configuration.client_certificate,
        client_key=secrets.client_configuration.client_key,
    ),
    machine_configuration_input=configuration.machine_configuration,
    node=master_vm_ipv4,
)


# resolve nested outputs, see https://github.com/pulumiverse/pulumi-talos/issues/93:
class ClientConfigurationArgs(t.Protocol):
    def __init__(self, *, ca_certificate, client_certificate, client_key):
        ...


def get_client_configuration_as[T: ClientConfigurationArgs](type_: type[T]) -> T:
    return type_(
        ca_certificate=secrets.client_configuration.ca_certificate,
        client_certificate=secrets.client_configuration.client_certificate,
        client_key=secrets.client_configuration.client_key,
    )


bootstrap = talos.machine.Bootstrap(
    f'{master_name}-talos-bootstrap',
    node=master_vm_ipv4,
    client_configuration=get_client_configuration_as(talos.machine.ClientConfigurationArgs),
    opts=pulumi.ResourceOptions(depends_on=[configuration_apply]),
)

kube_config = talos.cluster.get_kubeconfig_output(
    client_configuration=get_client_configuration_as(
        talos.cluster.GetKubeconfigClientConfigurationArgs
    ),
    node=master_vm_ipv4,
)

# # export to kube config with
# # p stack output --show-secrets k8s-master-0-dev-kube-config > ~/.kube/config
pulumi.export(f'{cluster_name}-kube-config', kube_config.kubeconfig_raw)

# wait for cluster to be ready:
talos.cluster.get_health_output(
    client_configuration=get_client_configuration_as(
        talos.cluster.GetHealthClientConfigurationArgs
    ),
    control_plane_nodes=[master_vm_ipv4],  # pyright: ignore[reportArgumentType]
    endpoints=[master_vm_ipv4],  # pyright: ignore[reportArgumentType]
)

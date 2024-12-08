"""Kubernetes stack."""

import json
import typing as t

import pulumi
import pulumiverse_talos as talos

from model import ConfigModel
from proxmox import create_vm_from_cdrom, download_iso, get_pve_provider, get_vm_ipv4

pulumi_config = pulumi.Config()
config = ConfigModel.model_validate(pulumi_config.require_object('config'))

pve_provider = get_pve_provider()

vm_boot_image = download_iso(
    name='vm-boot-image',
    node_name=config.node_name,
    url=str(config.talos_boot_image),
)

stack_name = pulumi.get_stack()
master_name = f'k8s-master-0-{stack_name}'

master_vm = create_vm_from_cdrom(
    name=master_name,
    config=config.control_plane_vms[0],
    node_name=config.node_name,
    boot_image=vm_boot_image,
)

master_vm_ipv4 = get_vm_ipv4(master_vm)
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

# wait for cluster to be fully initialized:
master_vm_ipv4.apply(
    lambda ipv4: talos.cluster.get_health_output(
        client_configuration=get_client_configuration_as(
            talos.cluster.GetHealthClientConfigurationArgs
        ),
        control_plane_nodes=[ipv4],
        endpoints=[ipv4],
    )
)

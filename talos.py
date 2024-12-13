"""Talos Linux utilities.

The output related typing in this module is a little weird, mainly to simplify use and work around
https://github.com/pulumiverse/pulumi-talos/issues/93.
"""
import collections.abc as c
import json
import typing as t

import pulumi
import pulumiverse_talos as talos

SCHEMATIC = """
customization:
    systemExtensions:
        officialExtensions:
            - siderolabs/qemu-guest-agent
"""
"""Schematic for images needed on Proxmox VM."""


def get_images() -> tuple[pulumi.Output[str], pulumi.Output[str]]:
    """Retrieve image URLs for needed configuration (hardcoded for now)."""

    schematic = talos.imagefactory.Schematic('talos-schematic', schematic=SCHEMATIC)

    urls = talos.imagefactory.get_urls_output(
        platform='metal',
        architecture='amd64',
        talos_version='v1.8.3',
        schematic_id=schematic.id,
    ).urls

    return urls.iso, urls.installer


class Configurations(t.NamedTuple):
    client: pulumi.Output[talos.machine.outputs.ClientConfiguration]
    controlplane: pulumi.Output[talos.machine.GetConfigurationResult]
    worker: pulumi.Output[talos.machine.GetConfigurationResult]
    talos: pulumi.Output[str]


# resolve nested outputs, see https://github.com/pulumiverse/pulumi-talos/issues/93:
class ClientConfigurationArgs(t.Protocol):
    def __init__(self, *, ca_certificate, client_certificate, client_key):
        ...


def _get_client_configuration_as[T: ClientConfigurationArgs](
    client_configuration: pulumi.Output[talos.machine.outputs.ClientConfiguration],
    type_: type[T],
) -> T:
    return type_(
        ca_certificate=client_configuration.ca_certificate,
        client_certificate=client_configuration.client_certificate,
        client_key=client_configuration.client_key,
    )


def get_configurations(
    cluster_name: str,
    cluster_endpoint: pulumi.Output[str],
    endpoints: pulumi.Output[c.Sequence[str]],
    nodes: pulumi.Output[c.Sequence[str]],
    image: pulumi.Input[str],
) -> Configurations:
    secrets = talos.machine.Secrets(f'{cluster_name}-talos-secrets')

    cp_node_config, wrk_node_config = (
        talos.machine.get_configuration_output(
            cluster_name=cluster_name,
            machine_type=machine_type,
            cluster_endpoint=cluster_endpoint,
            # resolve nested outputs, see https://github.com/pulumiverse/pulumi-talos/issues/93:
            machine_secrets=talos.machine.MachineSecretsArgs(
                certs=secrets.machine_secrets.certs,
                cluster=secrets.machine_secrets.cluster,
                secrets=secrets.machine_secrets.secrets,
                trustdinfo=secrets.machine_secrets.trustdinfo,
            ),
            config_patches=pulumi.Output.json_dumps(
                {
                    'machine': {
                        'install': {
                            'image': image,
                        }
                    }
                }
            ).apply(lambda o: [o]),
        )
        for machine_type in ('controlplane', 'worker')
    )

    client_configuration_detailed = talos.client.get_configuration_output(
        client_configuration=_get_client_configuration_as(
            secrets.client_configuration, talos.client.GetConfigurationClientConfigurationArgs
        ),
        cluster_name=cluster_name,
        endpoints=endpoints,
        nodes=nodes,
    )

    return Configurations(
        client=secrets.client_configuration,
        controlplane=cp_node_config,
        worker=wrk_node_config,
        talos=client_configuration_detailed.talos_config,
    )


def apply_machine_configuration(
    *,
    node_name: str,
    node_ipv4: pulumi.Input[str],
    client_configuration: pulumi.Output[talos.machine.outputs.ClientConfiguration],
    machine_configuration: pulumi.Input[str],
) -> talos.machine.ConfigurationApply:
    return talos.machine.ConfigurationApply(
        f'{node_name}-talos-configuration-apply',
        client_configuration=_get_client_configuration_as(
            client_configuration,
            talos.machine.ClientConfigurationArgs,
        ),
        machine_configuration_input=machine_configuration,
        config_patches=[
            json.dumps(
                {
                    'machine': {
                        'network': {
                            'hostname': node_name,
                        }
                    }
                }
            )
        ],
        node=node_ipv4,
    )


def bootstrap_cluster(
    *,
    name: str,
    node: pulumi.Input[str],
    client_configuration: pulumi.Output[talos.machine.outputs.ClientConfiguration],
    depends_on: list | None = None,
    wait=False,
) -> pulumi.Output[talos.cluster.GetKubeconfigResult]:
    talos.machine.Bootstrap(
        name,
        node=node,
        client_configuration=_get_client_configuration_as(
            client_configuration,
            talos.machine.ClientConfigurationArgs,
        ),
        opts=pulumi.ResourceOptions(depends_on=depends_on or []),
    )

    kube_config = talos.cluster.get_kubeconfig_output(
        client_configuration=_get_client_configuration_as(
            client_configuration,
            talos.cluster.GetKubeconfigClientConfigurationArgs,
        ),
        node=node,
    )

    if wait:
        # wait for cluster to be fully initialized:
        health = talos.cluster.get_health_output(
            client_configuration=_get_client_configuration_as(
                client_configuration,
                talos.cluster.GetHealthClientConfigurationArgs,
            ),
            control_plane_nodes=pulumi.Output.all(node),
            endpoints=pulumi.Output.all(node),
        )

        # make output kube config depend on health to be done:
        kube_config = pulumi.Output.all(kube_config, health).apply(
            lambda health_and_config: health_and_config[0]
        )

    return kube_config

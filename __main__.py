"""Kubernetes stack."""
import pulumi

from model import ConfigModel
from proxmox import create_vms_from_cdrom, download_iso, get_pve_provider
from talos import apply_machine_configuration, bootstrap_cluster, get_configurations, get_images

iso_image_url, installer_image_url = get_images()

pulumi_config = pulumi.Config()
config = ConfigModel.model_validate(pulumi_config.require_object('config'))

pve_provider = get_pve_provider()

vm_boot_image = download_iso(
    name='talos-boot-image',
    node_name=config.node_name,
    url=iso_image_url,
)

stack_name = pulumi.get_stack()

# create VMs for controlplane and workers
controlplane_address_by_name = create_vms_from_cdrom(
    pve_node_name=config.node_name,
    range_=config.controlplane_nodes,
    vm_name='cp',
    vm_boot_image=vm_boot_image,
    controlplane=True,
)
worker_address_by_name = create_vms_from_cdrom(
    pve_node_name=config.node_name,
    range_=config.worker_nodes,
    vm_name='wk',
    vm_boot_image=vm_boot_image,
    controlplane=False,
)

assert controlplane_address_by_name and worker_address_by_name

pulumi.export('controlplane-ipv4-addresses', controlplane_address_by_name)
pulumi.export('worker-ipv4-addresses', worker_address_by_name)

_, cluster_endpoint_address = next(iter(controlplane_address_by_name.items()))
cluster_endpoint = pulumi.Output.concat('https://', cluster_endpoint_address, ':6443')
cluster_name = 'common'
pulumi.export(f'{cluster_name}-endpoint', cluster_endpoint)

talos_configurations = get_configurations(
    cluster_name=cluster_name,
    cluster_endpoint=cluster_endpoint,
    endpoints=pulumi.Output.all(
        *controlplane_address_by_name.values(),
    ),
    nodes=pulumi.Output.all(
        *controlplane_address_by_name.values(),
        *worker_address_by_name.values(),
    ),
    image=installer_image_url,
)

pulumi.export('talos-client-config', talos_configurations.talos)

applied = []
for cp_node_name, cp_node_ipv4 in controlplane_address_by_name.items():
    applied.append(
        apply_machine_configuration(
            node_name=cp_node_name,
            node_ipv4=cp_node_ipv4,
            client_configuration=talos_configurations.client,
            machine_configuration=talos_configurations.controlplane.machine_configuration,
        )
    )
for cp_node_name, cp_node_ipv4 in worker_address_by_name.items():
    applied.append(
        apply_machine_configuration(
            node_name=cp_node_name,
            node_ipv4=cp_node_ipv4,
            client_configuration=talos_configurations.client,
            machine_configuration=talos_configurations.worker.machine_configuration,
        )
    )

kube_config = bootstrap_cluster(
    name=f'{cluster_name}-talos-bootstrap',
    client_configuration=talos_configurations.client,
    endpoint_node=cluster_endpoint_address,
    control_plane_nodes=controlplane_address_by_name.values(),
    worker_nodes=worker_address_by_name.values(),
    depends_on=applied,
    wait=False,
)

pulumi.export('kube-config', kube_config.kubeconfig_raw)

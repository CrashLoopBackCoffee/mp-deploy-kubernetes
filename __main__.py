"""Kubernetes stack."""
import pulumi

from model import ConfigModel
from proxmox import create_vm_from_cdrom, download_iso, get_pve_provider, get_vm_ipv4
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

cp_node_name = 'k8s-cp0'
stack_name = pulumi.get_stack()

cp_node_vm = create_vm_from_cdrom(
    name=f'{cp_node_name}-vm-{stack_name}',
    config=config.control_plane_vms[0],
    node_name=config.node_name,
    boot_image=vm_boot_image,
)

cp_node_ipv4 = get_vm_ipv4(cp_node_vm)
pulumi.export(f'{cp_node_name}-ipv4', cp_node_ipv4)

cluster_endpoint = pulumi.Output.concat('https://', cp_node_ipv4, ':6443')
cluster_name = 'common'
pulumi.export(f'{cluster_name}-endpoint', cluster_endpoint)

# right now we have one endpoint and that is also the single node:
nodes = cp_node_ipv4.apply(lambda ipv4: [ipv4])

talos_configurations = get_configurations(
    cluster_name=cluster_name,
    cluster_endpoint=cluster_endpoint,
    endpoints=nodes,
    nodes=nodes,
    image=installer_image_url,
)

pulumi.export('talos-client-config', talos_configurations.talos)

apply = apply_machine_configuration(
    node_name=cp_node_name,
    node_ipv4=cp_node_ipv4,
    client_configuration=talos_configurations.client,
    machine_configuration=talos_configurations.controlplane.machine_configuration,
)

kube_config = bootstrap_cluster(
    name=f'{cluster_name}-talos-bootstrap',
    client_configuration=talos_configurations.client,
    node=cp_node_ipv4,
    depends_on=[apply],
    wait=True,
)

pulumi.export('kube-config', kube_config.kubeconfig_raw)

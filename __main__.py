"""Kubernetes stack."""

import pulumi
import pulumi_proxmoxve

proxmox_stack = pulumi.StackReference(
    f'{pulumi.get_organization()}/deploy-proxmox/{pulumi.get_stack()}'
)

provider = pulumi_proxmoxve.Provider(
    'provider',
    endpoint=proxmox_stack.get_output('api-endpoint'),
    api_token=proxmox_stack.get_output('api-token'),
    insecure=proxmox_stack.get_output('api-insecure'),
)

node = pulumi_proxmoxve.get_node('pve-dev', opts=pulumi.InvokeOptions(provider=provider))
pulumi.export('node', node)

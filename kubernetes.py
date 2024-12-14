"""Kubernetes utilities."""
import pulumi
import pulumi_kubernetes as k8s


def remove_all_node_taints(node_name: str, k8s_provider: k8s.Provider):
    metadata = k8s.meta.v1.ObjectMetaPatchArgs(
        name=node_name,
        annotations={
            'pulumi.com/patchForce': 'true',
        },
    )
    opts = pulumi.ResourceOptions(
        provider=k8s_provider,
        retain_on_delete=True,
    )
    k8s.core.v1.NodePatch(
        f'{node_name}-untaint',
        metadata=metadata,
        spec=k8s.core.v1.NodeSpecPatchArgs(taints=[]),
        opts=opts,
    )

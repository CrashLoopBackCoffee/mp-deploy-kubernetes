import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.model import ComponentConfig


def ensure_csi_driver_smb(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    ns = k8s.core.v1.Namespace(
        'csi-driver-smb',
        metadata={
            'name': 'csi-driver-smb',
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'csi-driver-smb',
        kubeconfig=k8s_provider.kubeconfig,  # pyright: ignore[reportAttributeAccessIssue]
        namespace=ns.metadata.name,
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    k8s.helm.v3.Release(
        'csi-driver-smb',
        chart='csi-driver-smb',
        version=component_config.csi_driver_smb.version,
        repository_opts={
            'repo': 'https://raw.githubusercontent.com/kubernetes-csi/csi-driver-smb/master/charts'
        },
        values={
            # https://github.com/kubernetes-csi/csi-driver-smb/tree/master/charts#tips
            'linux': {'kubelet': '/var/snap/microk8s/common/var/lib/kubelet'},
        },
        opts=k8s_opts,
    )

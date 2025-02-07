"""Installation of metallb load balancer."""

import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.model import ComponentConfig


def ensure_cert_manager(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    ns = k8s.core.v1.Namespace(
        'cert-manager',
        metadata={
            'name': 'cert-manager',
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'cert-manager-provider',
        kubeconfig=k8s_provider.kubeconfig,  # pyright: ignore[reportAttributeAccessIssue]
        namespace=ns.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    # use Release instead of Chart in order to have one resource instead many individual:
    cert_manager = k8s.helm.v3.Release(
        'cert-manager',
        chart='cert-manager',
        version=component_config.microk8s.cert_manager.version,
        repository_opts={'repo': 'https://charts.jetstack.io'},
        values={
            'crds': {'enabled': True},
        },
        opts=k8s_opts,
    )

    # k8s.apiextensions.CustomResource(
    #     'default',
    #     api_version='metallb.io/v1beta1',
    #     kind='IPAddressPool',
    #     metadata={
    #         'name': 'default',
    #     },
    #     spec={
    #         'addresses': [
    #             '-'.join(
    #                 (
    #                     str(component_config.microk8s.metallb.ipv4_start),
    #                     str(component_config.microk8s.metallb.ipv4_end),
    #                 )
    #             )
    #         ],
    #     },
    #     opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[metallb])),
    # )

    # k8s.apiextensions.CustomResource(
    #     'default-l2-advertisment',
    #     api_version='metallb.io/v1beta1',
    #     kind='L2Advertisement',
    #     metadata={
    #         'name': 'default-l2-advertisment',
    #     },
    #     opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[metallb])),
    # )

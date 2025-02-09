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
        version=component_config.cert_manager.version,
        repository_opts={'repo': 'https://charts.jetstack.io'},
        values={
            'crds': {'enabled': True},
        },
        opts=k8s_opts,
    )

    cloudflare_secret = k8s.core.v1.Secret(
        'cloudflare-api-token',
        type='Opaque',
        string_data={'api-token': component_config.cloudflare.api_token.value},
        opts=k8s_opts,
    )

    k8s.apiextensions.CustomResource(
        'letsencrypt-issuer',
        api_version='cert-manager.io/v1',
        kind='ClusterIssuer',
        metadata={'name': 'lets-encrypt'},
        spec={
            'acme': {
                'server': component_config.cert_manager.acme_server,
                'email': component_config.cert_manager.acme_email,
                'privateKeySecretRef': {'name': 'lets-encrypt-private-key'},
                'solvers': [
                    {
                        'dns01': {
                            'cloudflare': {
                                'apiTokenSecretRef': {
                                    'name': cloudflare_secret.metadata.name,
                                    'key': 'api-token',
                                },
                            },
                        },
                    },
                ],
            },
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[cert_manager])),
    )

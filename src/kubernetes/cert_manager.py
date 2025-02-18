"""Installation of cert-manager."""

import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.model import ComponentConfig

LETS_ENCRYPT_SERVER_PROD = 'https://acme-v02.api.letsencrypt.org/directory'
LETS_ENCRYPT_SERVER_STAGING = 'https://acme-staging-v02.api.letsencrypt.org/directory'


def ensure_cert_manager(
    component_config: ComponentConfig, k8s_provider: k8s.Provider
) -> p.Resource:
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

    return _create_lets_encrypt_issuer(
        'lets-encrypt',
        component_config=component_config,
        server=LETS_ENCRYPT_SERVER_PROD,
        cloudflare_secret=cloudflare_secret,
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[cert_manager])),
    )


def _create_lets_encrypt_issuer(
    name: str,
    *,
    component_config: ComponentConfig,
    server: str,
    cloudflare_secret: k8s.core.v1.Secret,
    opts: p.ResourceOptions,
) -> k8s.apiextensions.CustomResource:
    return k8s.apiextensions.CustomResource(
        name,
        api_version='cert-manager.io/v1',
        kind='ClusterIssuer',
        metadata={'name': name},
        spec={
            'acme': {
                'server': server,
                'email': component_config.cert_manager.acme_email,
                'privateKeySecretRef': {'name': f'{name}-private-key'},
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
        opts=opts,
    )

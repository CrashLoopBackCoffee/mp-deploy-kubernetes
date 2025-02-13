"""Installation of traefik ingress controller."""

import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.model import ComponentConfig


def ensure_traefik(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    ns = k8s.core.v1.Namespace(
        'traefik',
        metadata={
            'name': 'traefik',
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'traefik-provider',
        kubeconfig=k8s_provider.kubeconfig,  # pyright: ignore[reportAttributeAccessIssue]
        namespace=ns.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    traefik = k8s.helm.v3.Release(
        'traefik',
        chart='traefik',
        version=component_config.traefik.version,
        repository_opts={'repo': 'https://traefik.github.io/charts'},
        values={
            'additionalArguments': [
                # expose the API directly from the pod to allow getting access to dashboard at
                # http://localhost:8080/ after kubectl port-forwarding:
                '--api.insecure=true',
            ]
        },
        opts=k8s_opts,
    )

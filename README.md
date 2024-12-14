# Kubernetes cluster on Proxmox

The cluster is set up by installing Talos Linux on VMs. The cluster name is `common-<stack>`, so for
the dev stack it is `common-dev`. After deployment, the following stack outputs can be used to
access the cluster:

- `talos-client-configuration` - Talos client configuration to be used with `talosctl`.
- `kube-config` - Kubeconfig to be used with `kubectl`.

```shell
p stack output --show-secrets talos-client-config > ~/.talos/config
p stack output --show-secrets kube-config > ~/.kube/config
```

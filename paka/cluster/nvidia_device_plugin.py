import pulumi
import pulumi_kubernetes as k8s


def install_nvidia_device_plugin(
    k8s_provider: k8s.Provider, version: str = "main"
) -> None:
    """
    Installs the NVIDIA device plugin for GPU support in the cluster.

    This function deploys the NVIDIA device plugin to the cluster using a DaemonSet.
    The device plugin allows Kubernetes to discover and manage GPU resources on the nodes.

    Args:
        k8s_provider (k8s.Provider): The Kubernetes provider to use for deploying the device plugin.

    Returns:
        None
    """
    # This will install a DaemonSet in the kube-system namespace
    k8s.yaml.ConfigFile(
        "nvidia-device-plugin",
        file=f"https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/{version}/nvidia-device-plugin.yml",
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

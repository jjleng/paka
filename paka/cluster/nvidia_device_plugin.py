import pulumi
import pulumi_kubernetes as k8s

from paka.cluster.context import Context
from paka.utils import call_once


@call_once
def install_nvidia_device_plugin(ctx: Context, version: str = "v0.15.0-rc.2") -> None:
    """
    Installs the NVIDIA device plugin for GPU support in the cluster.

    This function deploys the NVIDIA device plugin to the cluster using a DaemonSet.
    The device plugin allows Kubernetes to discover and manage GPU resources on the nodes.

    Args:
        k8s_provider (k8s.Provider): The Kubernetes provider to use for deploying the device plugin.

    Returns:
        None
    """

    k8s.apps.v1.DaemonSet(
        "nvidia-device-plugin-daemonset",
        metadata=k8s.meta.v1.ObjectMetaArgs(
            namespace="kube-system",
        ),
        spec=k8s.apps.v1.DaemonSetSpecArgs(
            selector=k8s.meta.v1.LabelSelectorArgs(
                match_labels={
                    "name": "nvidia-device-plugin-ds",
                },
            ),
            update_strategy=k8s.apps.v1.DaemonSetUpdateStrategyArgs(
                type="RollingUpdate",
            ),
            template=k8s.core.v1.PodTemplateSpecArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    labels={
                        "name": "nvidia-device-plugin-ds",
                    },
                ),
                spec=k8s.core.v1.PodSpecArgs(
                    tolerations=[
                        k8s.core.v1.TolerationArgs(
                            key="nvidia.com/gpu",
                            operator="Exists",
                            effect="NoSchedule",
                        ),
                        k8s.core.v1.TolerationArgs(operator="Exists"),
                    ],
                    priority_class_name="system-node-critical",
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            image=f"nvcr.io/nvidia/k8s-device-plugin:{version}",
                            name="nvidia-device-plugin-ctr",
                            env=[
                                k8s.core.v1.EnvVarArgs(
                                    name="FAIL_ON_INIT_ERROR",
                                    value="false",
                                )
                            ],
                            security_context=k8s.core.v1.SecurityContextArgs(
                                allow_privilege_escalation=False,
                                capabilities=k8s.core.v1.CapabilitiesArgs(
                                    drop=["ALL"],
                                ),
                            ),
                            volume_mounts=[
                                k8s.core.v1.VolumeMountArgs(
                                    name="device-plugin",
                                    mount_path="/var/lib/kubelet/device-plugins",
                                )
                            ],
                        )
                    ],
                    volumes=[
                        k8s.core.v1.VolumeArgs(
                            name="device-plugin",
                            host_path=k8s.core.v1.HostPathVolumeSourceArgs(
                                path="/var/lib/kubelet/device-plugins",
                            ),
                        )
                    ],
                ),
            ),
        ),
        opts=pulumi.ResourceOptions(provider=ctx.k8s_provider),
    )

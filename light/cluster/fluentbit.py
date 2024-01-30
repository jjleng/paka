import pulumi
import pulumi_kubernetes as k8s

from light.constants import ACCESS_ALL_SA, APP_NS
from light.utils import call_once


@call_once
def create_fluentbit(fluent_bit_config: str, k8s_provider: k8s.Provider) -> None:
    """
    Creates a fluentbit daemonset with the given configuration.
    """

    parsers_config = """
[PARSER]
    Name        docker
    Format      json
    Time_Key    time
    Time_Format %Y-%m-%dT%H:%M:%S.%fZ
"""
    parsers_config_map = k8s.core.v1.ConfigMap(
        "fluent-bit-parsers",
        data={"parsers.conf": parsers_config},
        metadata={"namespace": APP_NS, "name": "fluent-bit-parsers"},
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    fluent_bit_config_map = k8s.core.v1.ConfigMap(
        "fluent-bit-config-map",
        data={"fluent-bit.conf": fluent_bit_config},
        metadata={
            "namespace": APP_NS,
            "name": "fluent-bit-config",
        },
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    k8s.apps.v1.DaemonSet(
        "fluent-bit-daemonset",
        spec=k8s.apps.v1.DaemonSetSpecArgs(
            selector=k8s.meta.v1.LabelSelectorArgs(
                match_labels={"k8s-app": "fluent-bit-logging"},
            ),
            template=k8s.core.v1.PodTemplateSpecArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    labels={"k8s-app": "fluent-bit-logging"},
                ),
                spec=k8s.core.v1.PodSpecArgs(
                    service_account_name=ACCESS_ALL_SA,
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            name="fluent-bit",
                            image="fluent/fluent-bit:latest",
                            volume_mounts=[
                                k8s.core.v1.VolumeMountArgs(
                                    name="config",
                                    mount_path="/fluent-bit/etc/fluent-bit.conf",
                                    sub_path="fluent-bit.conf",
                                ),
                                k8s.core.v1.VolumeMountArgs(
                                    name="varlog",
                                    mount_path="/var/log",
                                ),
                                k8s.core.v1.VolumeMountArgs(
                                    name="varlibdockercontainers",
                                    mount_path="/var/lib/docker/containers",
                                    read_only=True,
                                ),
                                k8s.core.v1.VolumeMountArgs(
                                    name="parsers-config",
                                    mount_path="/fluent-bit/etc/parsers.conf",
                                    sub_path="parsers.conf",
                                ),
                            ],
                        )
                    ],
                    volumes=[
                        k8s.core.v1.VolumeArgs(
                            name="config",
                            config_map=k8s.core.v1.ConfigMapVolumeSourceArgs(
                                name=fluent_bit_config_map.metadata["name"],
                            ),
                        ),
                        k8s.core.v1.VolumeArgs(
                            name="varlog",
                            host_path=k8s.core.v1.HostPathVolumeSourceArgs(
                                path="/var/log",
                            ),
                        ),
                        k8s.core.v1.VolumeArgs(
                            name="varlibdockercontainers",
                            host_path=k8s.core.v1.HostPathVolumeSourceArgs(
                                path="/var/lib/docker/containers",
                            ),
                        ),
                        k8s.core.v1.VolumeArgs(
                            name="parsers-config",
                            config_map=k8s.core.v1.ConfigMapVolumeSourceArgs(
                                name=parsers_config_map.metadata["name"],
                            ),
                        ),
                    ],
                ),
            ),
        ),
        metadata={"namespace": APP_NS},
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

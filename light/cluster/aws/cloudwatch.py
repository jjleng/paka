import json

import pulumi_aws as aws
import pulumi_kubernetes as k8s

from light.constants import ACCESS_ALL_SA, APP_NS, PROJECT_NAME

LOG_GROUP = f"EKSContainerLogs/{PROJECT_NAME}"

cloudwatch_agent_config = json.dumps(
    {
        "agent": {"metrics_collection_interval": 60, "run_as_user": 0},
        "metrics": {
            "append_dimensions": {
                "ImageId": "${aws:ImageId}",
                "InstanceId": "${aws:InstanceId}",
                "InstanceType": "${aws:InstanceType}",
            },
            "metrics_collected": {
                "cpu": {
                    "measurement": [
                        "cpu_usage_idle",
                        "cpu_usage_iowait",
                        "cpu_usage_user",
                        "cpu_usage_system",
                    ],
                    "metrics_collection_interval": 60,
                    "totalcpu": False,
                },
                "disk": {
                    "measurement": ["disk_used_percent"],
                    "metrics_collection_interval": 60,
                    "resources": ["*"],
                },
                "mem": {
                    "measurement": ["mem_used_percent"],
                    "metrics_collection_interval": 60,
                },
            },
        },
        "logs": {
            "logs_collected": {
                "files": {
                    "collect_list": [
                        {
                            "file_path": "/var/log/containers/*.log",
                            "log_group_name": LOG_GROUP,
                            "log_stream_name": "{instance_id}/{container_id}",
                            "timestamp_format": "%Y-%m-%dT%H:%M:%S.%fZ",
                        }
                    ]
                }
            }
        },
    }
)

log_group = aws.cloudwatch.LogGroup("my-log-group")


cloudwatch_agent_config_map = k8s.core.v1.ConfigMap(
    "cloudwatch-agent-config-map",
    data={"cwagentconfig.json": cloudwatch_agent_config},
    metadata={
        "namespace": APP_NS,
        "name": "cwagentconfig",
    },
)

cloudwatch_agent_daemonset = k8s.apps.v1.DaemonSet(
    "cloudwatch-agent-daemonset",
    spec=k8s.apps.v1.DaemonSetSpecArgs(
        selector=k8s.meta.v1.LabelSelectorArgs(
            match_labels={"name": "cloudwatch-agent"},
        ),
        template=k8s.core.v1.PodTemplateSpecArgs(
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels={"name": "cloudwatch-agent"},
            ),
            spec=k8s.core.v1.PodSpecArgs(
                service_account_name=ACCESS_ALL_SA,
                containers=[
                    k8s.core.v1.ContainerArgs(
                        name="cloudwatch-agent",
                        image="amazon/cloudwatch-agent:latest",
                        volume_mounts=[
                            k8s.core.v1.VolumeMountArgs(
                                name="cwagentconfig",
                                mount_path="/etc/cwagentconfig",
                            )
                        ],
                    )
                ],
                volumes=[
                    k8s.core.v1.VolumeArgs(
                        name="cwagentconfig",
                        config_map=k8s.core.v1.ConfigMapVolumeSourceArgs(
                            name=cloudwatch_agent_config_map.metadata["name"],
                        ),
                    )
                ],
            ),
        ),
    ),
    metadata={"namespace": APP_NS, "name": "cloudwatch-agent"},
)

import pulumi_aws as aws
import pulumi_kubernetes as k8s

from cusco.cluster.fluentbit import create_fluentbit
from cusco.config import CloudConfig
from cusco.constants import PROJECT_NAME

LOG_GROUP = f"EKSContainerLogs/{PROJECT_NAME}"


def enable_cloudwatch(cloud_config: CloudConfig, k8s_provider: k8s.Provider) -> None:
    aws.cloudwatch.LogGroup(
        "log-group",
        name=LOG_GROUP,
        retention_in_days=cloud_config.cluster.logRetentionDays,
    )

    # Fluent Bit configuration for forwarding logs to CloudWatch
    fluent_bit_config = f"""
[SERVICE]
    Parsers_File /fluent-bit/etc/parsers.conf

[INPUT]
    Name              tail
    Path              /var/log/containers/*.log
    Parser            docker
    Tag               kube.*
    Refresh_Interval  5

[OUTPUT]
    Name               cloudwatch_logs
    Match              kube.*
    log_group_name     {LOG_GROUP}
    log_stream_prefix  eks/
    region             {cloud_config.cluster.region}
"""
    create_fluentbit(fluent_bit_config, k8s_provider)

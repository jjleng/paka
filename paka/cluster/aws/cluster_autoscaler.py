import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes.helm.v3 as helm
from pulumi_kubernetes.core.v1 import ConfigMap

from paka.cluster.aws.utils import odic_role_for_sa
from paka.cluster.context import Context
from paka.utils import call_once, to_yaml


def create_priority_expander(ctx: Context) -> ConfigMap:
    # Create a priority expander to ensure that the cluster autoscaler provisions spot instances first.
    priority_data = {10: [".*spot.*"], 1: [".*"]}
    return ConfigMap(
        "cluster-autoscaler-priority-expander",
        metadata={
            "name": "cluster-autoscaler-priority-expander",
            "namespace": "kube-system",
        },
        data={
            "priorities": to_yaml(priority_data),
        },
        opts=pulumi.ResourceOptions(provider=ctx.k8s_provider),
    )


@call_once
def create_cluster_autoscaler(
    ctx: Context,
    cluster: eks.Cluster,
) -> None:
    """
    Sets up the cluster autoscaler for an EKS cluster.

    Args:
        cluster (eks.Cluster): The EKS cluster.
        k8s_provider (k8s.Provider): The Kubernetes provider.
        config (CloudConfig): The cluster config provided by user.

    Returns:
        None
    """
    cluster_name = ctx.cluster_name

    autoscaler_policy_doc = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                actions=[
                    "autoscaling:DescribeAutoScalingGroups",
                    "autoscaling:DescribeAutoScalingInstances",
                    "autoscaling:DescribeLaunchConfigurations",
                    "autoscaling:DescribeTags",
                    "autoscaling:SetDesiredCapacity",
                    "autoscaling:TerminateInstanceInAutoScalingGroup",
                    "ec2:DescribeLaunchTemplateVersions",
                    "eks:DescribeNodegroup",
                    "ec2:GetInstanceTypesFromInstanceRequirements",
                    "ec2:DescribeImages",
                ],
                resources=["*"],
            )
        ]
    )

    autoscaler_policy = aws.iam.Policy(
        f"{cluster_name}-autoscaler-policy", policy=autoscaler_policy_doc.json
    )

    # The OIDC provider is required because the cluster autoscaler runs within the Kubernetes
    # cluster and needs to interact with the AWS API to manage the Auto Scaling Groups (ASGs).
    # OIDC provides a secure mechanism for the cluster autoscaler to authenticate with the AWS API.
    autoscaler_role = odic_role_for_sa(
        ctx, cluster, "autoscaler", "kube-system:cluster-autoscaler"
    )

    aws.iam.RolePolicyAttachment(
        f"{cluster_name}-autoscaler-role-policy-attachment",
        policy_arn=autoscaler_policy.arn,
        role=autoscaler_role.name,
    )

    expander = create_priority_expander(ctx)

    helm.Chart(
        "cluster-autoscaler",
        helm.ChartOpts(
            chart="cluster-autoscaler",
            version="9.34.0",
            namespace="kube-system",
            fetch_opts=helm.FetchOpts(repo="https://kubernetes.github.io/autoscaler"),
            values={
                "autoDiscovery": {"clusterName": cluster.eks_cluster.name},
                "awsRegion": ctx.region,
                "rbac": {
                    "create": True,
                    "serviceAccount": {
                        "create": True,
                        "name": "cluster-autoscaler",
                        "annotations": {
                            "eks.amazonaws.com/role-arn": autoscaler_role.arn
                        },
                    },
                },
                "serviceMonitor": {"interval": "2s"},
                "image": {"tag": "v1.28.2"},
                "extraArgs": {
                    "expander": "priority,random",  # Use priority expander if possible
                },
            },
        ),
        opts=pulumi.ResourceOptions(provider=ctx.k8s_provider, depends_on=[expander]),
    )

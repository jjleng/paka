import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm

from paka.cluster.aws.utils import odic_role_for_sa
from paka.config import CloudConfig
from paka.utils import call_once


@call_once
def create_cluster_autoscaler(
    config: CloudConfig,
    cluster: eks.Cluster,
    k8s_provider: k8s.Provider,
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
    project = config.cluster.name

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
                ],
                resources=["*"],
            )
        ]
    )

    autoscaler_policy = aws.iam.Policy(
        f"{project}-autoscaler-policy", policy=autoscaler_policy_doc.json
    )

    # The OIDC provider is required because the cluster autoscaler runs within the Kubernetes
    # cluster and needs to interact with the AWS API to manage the Auto Scaling Groups (ASGs).
    # OIDC provides a secure mechanism for the cluster autoscaler to authenticate with the AWS API.
    autoscaler_role = odic_role_for_sa(
        config, cluster, "autoscaler", "kube-system:cluster-autoscaler"
    )

    aws.iam.RolePolicyAttachment(
        f"{project}-autoscaler-role-policy-attachment",
        policy_arn=autoscaler_policy.arn,
        role=autoscaler_role.name,
    )

    helm.Chart(
        "cluster-autoscaler",
        helm.ChartOpts(
            chart="cluster-autoscaler",
            version="9.34.0",
            namespace="kube-system",
            fetch_opts=helm.FetchOpts(repo="https://kubernetes.github.io/autoscaler"),
            values={
                "autoDiscovery": {"clusterName": cluster.eks_cluster.name},
                "awsRegion": config.cluster.region,
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
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

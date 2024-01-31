import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes as k8s

from light.cluster.aws.utils import odic_role_for_sa
from light.config import CloudConfig
from light.constants import ACCESS_ALL_SA
from light.utils import call_once, read_cluster_data, read_current_cluster_data

APP_NS = read_current_cluster_data("namespace")


@call_once
def create_service_accounts(
    config: CloudConfig,
    cluster: eks.Cluster,
    k8s_provider: k8s.Provider,
) -> None:
    """
    Creates service accounts with necessary IAM roles and policies.

    This function creates two IAM policies: one for S3 access and one for ECR access.
    It then creates an IAM role for the service account and attaches the two policies to this role.
    Finally, it creates a Kubernetes service account and annotates it with the ARN of the IAM role.

    The S3 policy allows the service account to get objects and list the bucket.
    The ECR policy allows the service account to perform various actions related to ECR images.

    Args:
        config (CloudConfig): The cloud configuration containing the cluster name.
        cluster (eks.Cluster): The EKS cluster to create the service accounts in.
        k8s_provider (k8s.Provider): The Kubernetes provider to use when creating the service account.

    Returns:
        None
    """
    project = config.cluster.name
    bucket = read_cluster_data(project, "bucket")

    s3_policy = aws.iam.Policy(
        f"{project}-s3-access-policy",
        policy=aws.iam.get_policy_document(
            statements=[
                aws.iam.GetPolicyDocumentStatementArgs(
                    effect="Allow",
                    actions=["s3:GetObject", "s3:ListBucket"],
                    resources=[
                        f"arn:aws:s3:::{bucket}/*",
                        f"arn:aws:s3:::{bucket}",
                    ],
                )
            ]
        ).json,
    )

    ecr_policy = aws.iam.Policy(
        f"{project}-ecr-access-policy",
        policy=aws.iam.get_policy_document(
            statements=[
                aws.iam.GetPolicyDocumentStatementArgs(
                    effect="Allow",
                    actions=[
                        "ecr:GetDownloadUrlForLayer",
                        "ecr:BatchGetImage",
                        "ecr:BatchCheckLayerAvailability",
                        "ecr:ListImages",
                        "ecr:DescribeImages",
                    ],
                    resources=["*"],
                )
            ]
        ).json,
    )

    cloudwatch_policy = aws.iam.Policy(
        "cloudwatch-policy",
        policy=aws.iam.get_policy_document(
            statements=[
                aws.iam.GetPolicyDocumentStatementArgs(
                    effect="Allow",
                    actions=[
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogStreams",
                    ],
                    resources=["arn:aws:logs:*:*:*"],
                )
            ]
        ).json,
    )

    sa_role = odic_role_for_sa(config, cluster, "sa", f"{APP_NS}:{ACCESS_ALL_SA}")

    aws.iam.RolePolicyAttachment(
        f"{project}-sa-s3-role-policy-attachment",
        role=sa_role.name,
        policy_arn=s3_policy.arn,
    )

    aws.iam.RolePolicyAttachment(
        f"{project}-sa-ecr-role-policy-attachment",
        role=sa_role.name,
        policy_arn=ecr_policy.arn,
    )

    aws.iam.RolePolicyAttachment(
        f"{project}-sa-cloudwatch-role-policy-attachment",
        role=sa_role.name,
        policy_arn=cloudwatch_policy.arn,
    )

    k8s.core.v1.ServiceAccount(
        f"{project}-service-account",
        metadata={
            "namespace": APP_NS,
            "name": ACCESS_ALL_SA,
            "annotations": {"eks.amazonaws.com/role-arn": sa_role.arn},
        },
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

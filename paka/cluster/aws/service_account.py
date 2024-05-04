import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes as k8s

from paka.cluster.aws.utils import odic_role_for_sa
from paka.cluster.context import Context
from paka.constants import ACCESS_ALL_SA
from paka.utils import call_once


@call_once
def create_service_accounts(
    ctx: Context,
    cluster: eks.Cluster,
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
    cluster_name = ctx.cluster_name
    bucket = ctx.bucket

    s3_policy = aws.iam.Policy(
        f"{cluster_name}-s3-access-policy",
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
        f"{cluster_name}-ecr-access-policy",
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

    namespace = ctx.namespace
    sa_role = odic_role_for_sa(
        ctx,
        cluster,
        "sa",
        f"{namespace}:{ACCESS_ALL_SA}",
    )

    aws.iam.RolePolicyAttachment(
        f"{cluster_name}-sa-s3-role-policy-attachment",
        role=sa_role.name,
        policy_arn=s3_policy.arn,
    )

    aws.iam.RolePolicyAttachment(
        f"{cluster_name}-sa-ecr-role-policy-attachment",
        role=sa_role.name,
        policy_arn=ecr_policy.arn,
    )

    aws.iam.RolePolicyAttachment(
        f"{cluster_name}-sa-cloudwatch-role-policy-attachment",
        role=sa_role.name,
        policy_arn=cloudwatch_policy.arn,
    )

    k8s.core.v1.ServiceAccount(
        f"{cluster_name}-service-account",
        metadata={
            "namespace": ctx.namespace,
            "name": ACCESS_ALL_SA,
            "annotations": {"eks.amazonaws.com/role-arn": sa_role.arn},
        },
        opts=pulumi.ResourceOptions(provider=ctx.k8s_provider),
    )

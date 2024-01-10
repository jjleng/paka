import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes as k8s

from light.cluster.aws.utils import odic_role_for_sa
from light.config import CloudConfig
from light.constants import ACCESS_ALL_SA, APP_NS
from light.utils import call_once, read_cluster_data


@call_once
def create_service_accounts(
    config: CloudConfig,
    cluster: eks.Cluster,
    k8s_provider: k8s.Provider,
) -> None:
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

    k8s.core.v1.ServiceAccount(
        f"{project}-service-account",
        metadata={
            "namespace": APP_NS,
            "name": ACCESS_ALL_SA,
            "annotations": {"eks.amazonaws.com/role-arn": sa_role.arn},
        },
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

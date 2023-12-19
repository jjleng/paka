import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
import pulumi_kubernetes as k8s
from light.cluster.config import CloudConfig
from light.cluster.aws.utils import odic_role_for_sa
from light.constants import SERVICE_ACCOUNT


def create_service_account(
    config: CloudConfig,
    cluster: eks.Cluster,
    k8s_provider: k8s.Provider,
) -> None:
    project = config.cluster.name
    bucket = project

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

    sa_role = odic_role_for_sa(config, cluster, "sa", f"default:{SERVICE_ACCOUNT}")

    aws.iam.RolePolicyAttachment(
        f"{project}-sa-role-policy-attachment",
        role=sa_role.name,
        policy_arn=s3_policy.arn,
    )

    k8s.core.v1.ServiceAccount(
        f"{project}-service-account",
        metadata={
            "namespace": "default",
            "name": SERVICE_ACCOUNT,
            "annotations": {"eks.amazonaws.com/role-arn": sa_role.arn},
        },
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

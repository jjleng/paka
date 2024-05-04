import pulumi
import pulumi_aws as aws
import pulumi_eks as eks

from paka.cluster.context import Context


def odic_role_for_sa(
    ctx: Context,
    cluster: eks.Cluster,
    role_name: str,
    ns_service_account: str,
) -> aws.iam.Role:
    """
    Creates an IAM role for a service account in an EKS cluster using OpenID Connect (OIDC) authentication.

    Args:
        config (CloudConfig): The cloud configuration.
        cluster (eks.Cluster): The EKS cluster.
        role_name (str): The name of the role.
        ns_service_account (str): The name of the service account. e.g. "default:sa", "kube-system:auto-scaler"

    Returns:
        aws.iam.Role: The IAM role for the service account.
    """
    oidc_url = cluster.core.oidc_provider.url
    oidc_arn = cluster.core.oidc_provider.arn

    assume_role_policy = pulumi.Output.all(oidc_url, oidc_arn).apply(
        lambda args: aws.iam.get_policy_document(
            statements=[
                aws.iam.GetPolicyDocumentStatementArgs(
                    effect="Allow",
                    principals=[
                        aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                            type="Federated",
                            identifiers=[str(args[1])],
                        )
                    ],
                    actions=["sts:AssumeRoleWithWebIdentity"],
                    conditions=[
                        aws.iam.GetPolicyDocumentStatementConditionArgs(
                            test="StringEquals",
                            variable=f"{args[0]}:sub",
                            values=[f"system:serviceaccount:{ns_service_account}"],
                        )
                    ],
                )
            ],
        ).json
    )

    role = aws.iam.Role(
        f"{ctx.cluster_name}-{role_name}-role",
        assume_role_policy=assume_role_policy,
    )

    return role

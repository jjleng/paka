from light.config import CloudConfig
import pulumi_eks as eks
import pulumi_aws as aws


def odic_role_for_sa(
    config: CloudConfig,
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
    project = config.cluster.name

    role = aws.iam.Role(
        f"{project}-{role_name}-role",
        assume_role_policy=cluster.core.oidc_provider.url.apply(
            lambda url: aws.iam.get_policy_document(
                statements=[
                    aws.iam.GetPolicyDocumentStatementArgs(
                        effect="Allow",
                        principals=[
                            aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                                type="Federated",
                                identifiers=[cluster.core.oidc_provider.arn],
                            )
                        ],
                        actions=["sts:AssumeRoleWithWebIdentity"],
                        conditions=[
                            aws.iam.GetPolicyDocumentStatementConditionArgs(
                                test="StringEquals",
                                variable=f"{url}:sub",
                                values=[f"system:serviceaccount:{ns_service_account}"],
                            )
                        ],
                    )
                ],
            ).json
        ),
    )

    return role

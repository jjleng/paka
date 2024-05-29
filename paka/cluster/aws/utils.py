from __future__ import annotations

from typing import Sequence

import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
from pulumi import Input

from paka.cluster.context import Context
from paka.utils import get_instance_info


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


def get_ami_for_instance(ctx: Context, instance_type: str) -> str:
    instance_info = get_instance_info(ctx.provider, ctx.region, instance_type)
    gpu_count = instance_info.get("gpu_count", 0) or 0
    arch = instance_info.get("arch", "x86_64")

    if gpu_count > 0:
        if arch == "x86_64":
            return "AL2_x86_64_GPU"
        else:
            return "BOTTLEROCKET_ARM_64_NVIDIA"
    else:
        if arch == "arm64":
            return "AL2_ARM_64"
    return "AL2_x86_64"


def create_vpc_endpoint_for_s3(
    vpc_id: str, route_table_ids: Input[Sequence[Input[str]]], region: str
) -> aws.ec2.VpcEndpoint:
    s3_service_name = f"com.amazonaws.{region}.s3"

    vpc_endpoint = aws.ec2.VpcEndpoint(
        "s3-vpc-endpoint",
        vpc_id=vpc_id,
        service_name=s3_service_name,
        route_table_ids=route_table_ids,
    )
    return vpc_endpoint

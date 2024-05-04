import pulumi
import pulumi_aws as aws
import pulumi_eks as eks
from pulumi_kubernetes.helm.v3 import Chart, ChartOpts, FetchOpts

from paka.cluster.aws.utils import odic_role_for_sa
from paka.cluster.context import Context
from paka.utils import call_once


@call_once
def create_ebs_csi_driver(ctx: Context, cluster: eks.Cluster) -> None:
    cluster_name = ctx.cluster_name

    csi_driver_policy_doc = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                actions=[
                    "ec2:CreateSnapshot",
                    "ec2:AttachVolume",
                    "ec2:DetachVolume",
                    "ec2:ModifyVolume",
                    "ec2:DescribeAvailabilityZones",
                    "ec2:DescribeInstances",
                    "ec2:DescribeSnapshots",
                    "ec2:DescribeTags",
                    "ec2:DescribeVolumes",
                    "ec2:DescribeVolumesModifications",
                    "ec2:CreateTags",
                    "ec2:CreateVolume",
                    "ec2:DeleteVolume",
                ],
                resources=["*"],
                effect="Allow",
            )
        ]
    )

    csi_driver_policy = aws.iam.Policy(
        f"{cluster_name}-csi-driver-policy", policy=csi_driver_policy_doc.json
    )

    csi_driver_role = odic_role_for_sa(
        ctx, cluster, "csi-driver", "kube-system:ebs-csi-controller-sa"
    )

    aws.iam.RolePolicyAttachment(
        f"{cluster_name}-csi-driver-role-policy-attachment",
        policy_arn=csi_driver_policy.arn,
        role=csi_driver_role.name,
    )

    Chart(
        "aws-ebs-csi-driver",
        ChartOpts(
            chart="aws-ebs-csi-driver",
            version="2.26.0",
            namespace="kube-system",
            fetch_opts=FetchOpts(
                repo="https://kubernetes-sigs.github.io/aws-ebs-csi-driver"
            ),
            values={
                "controller": {
                    "serviceAccount": {
                        "create": "true",
                        "name": "ebs-csi-controller-sa",
                        "annotations": {
                            "eks.amazonaws.com/role-arn": csi_driver_role.arn
                        },
                        "automountServiceAccountToken": "true",
                    },
                }
            },
        ),
        opts=pulumi.ResourceOptions(provider=ctx.k8s_provider),
    )

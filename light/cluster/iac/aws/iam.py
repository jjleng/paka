from pulumi_aws import iam
from light.cluster.iac.aws.s3 import s3_bucket


def iam_user(cluster_name: str) -> iam.User:
    # Bucket has the same name as the cluster
    s3 = s3_bucket(cluster_name)

    # Create an IAM user
    user = iam.User(cluster_name)

    # IAM policy document allowing access to S3 and EC2
    iam_policy_document = iam.get_policy_document(
        statements=[
            iam.GetPolicyDocumentStatementArgs(
                actions=["s3:*"],
                resources=[s3.arn],
            ),
            iam.GetPolicyDocumentStatementArgs(
                actions=["ec2:*"],
                resources=["*"],
            ),
        ]
    )

    # Create an IAM policy
    iam_policy = iam.Policy(f"{cluster_name}-policy", policy=iam_policy_document.json)

    # Attach the policy to the user
    iam.UserPolicyAttachment(
        f"{cluster_name}-policy-attachment",
        user=user.name,
        policy_arn=iam_policy.arn,
    )

    return user

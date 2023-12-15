import pulumi
from pulumi_aws import s3, iam, ec2
from light.cluster.config import CloudConfig


def get_cluster_name(config: CloudConfig) -> str:
    return config.cluster.name


def s3_bucket(cluster_name: str) -> s3.Bucket:
    bucket = s3.Bucket(cluster_name)

    pulumi.export("bucket_name", bucket.id)

    return bucket


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


def create_vpc(config: CloudConfig) -> ec2.Vpc:
    cluster_name = get_cluster_name(config)

    # Create a VPC
    vpc = ec2.Vpc(f"{cluster_name}-vpc", cidr_block="10.0.0.0/16")

    return vpc


def create_public_subnet(config: CloudConfig, vpc: ec2.Vpc) -> ec2.Subnet:
    cluster_name = get_cluster_name(config)

    # Create a public Subnet
    public_subnet = ec2.Subnet(
        f"{cluster_name}-public-subnet",
        vpc_id=vpc.id,
        cidr_block="10.0.1.0/24",
        map_public_ip_on_launch=True,
    )  # Public subnet

    # Create an Internet Gateway
    igw = ec2.InternetGateway(f"{cluster_name}-igw", vpc_id=vpc.id)

    # Create a Route Table for public subnet
    public_route_table = ec2.RouteTable(
        f"{cluster_name}-public-route-table", vpc_id=vpc.id
    )
    ec2.RouteTableAssociation(
        f"{cluster_name}-public-route-table-association",
        route_table_id=public_route_table.id,
        subnet_id=public_subnet.id,
    )
    ec2.Route(
        f"{cluster_name}-public-route",
        route_table_id=public_route_table.id,
        destination_cidr_block="0.0.0.0/0",
        gateway_id=igw.id,
    )
    return public_subnet


def create_private_subnet(config: CloudConfig, vpc: ec2.Vpc) -> ec2.Subnet:
    cluster_name = get_cluster_name(config)

    # Create a private Subnet
    private_subnet = ec2.Subnet(
        f"{cluster_name}-private-subnet", vpc_id=vpc.id, cidr_block="10.0.2.0/24"
    )  # Private subnet

    return private_subnet

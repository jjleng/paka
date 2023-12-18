import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
import pulumi_eks as eks
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm
from light.cluster.config import CloudConfig

SERVICE_ACCOUNT = "light-sa"


def _ignore_tags_transformation(
    args: pulumi.ResourceTransformationArgs,
) -> pulumi.ResourceTransformationResult | None:
    """
    EKS adds tags to VPC and Subnet resources that are not managed by Pulumi. This function ignores those tags so that Pulumi does not try to remove them.

    Args:
        args (pulumi.ResourceTransformationArgs): The arguments containing the resource properties and options.

    Returns:
        pulumi.ResourceTransformationResult | None: The transformed resource properties and options, or None if no transformation is needed.
    """
    if args.type_ == "aws:ec2/vpc:Vpc" or args.type_ == "aws:ec2/subnet:Subnet":
        return pulumi.ResourceTransformationResult(
            props=args.props,
            opts=pulumi.ResourceOptions.merge(
                args.opts, pulumi.ResourceOptions(ignore_changes=["tags"])
            ),
        )
    return None


def create_node_group_for_model_group(
    config: CloudConfig,
    cluster: eks.Cluster,
    vpc: awsx.ec2.Vpc,
    worker_role: aws.iam.Role,
) -> None:
    if config.modelGroups is None:
        return

    project = config.cluster.name

    for model_group in config.modelGroups:
        # Create a managed node group for our cluster
        eks.ManagedNodeGroup(
            f"{project}-{model_group.name}-group",
            node_group_name=f"{project}-{model_group.name}-group",
            cluster=cluster,
            instance_types=[model_group.nodeType],
            scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                desired_size=1,
                # No scale down to 0 for now
                min_size=1,
                max_size=model_group.replica,
            ),
            labels={"size": model_group.nodeType, "group": model_group.name},
            node_role_arn=worker_role.arn,
            subnet_ids=vpc.private_subnet_ids,
        )


# Creates an AWS IAM Role named 'role_name'.
# This role uses Web Identity Federation for authentication, leveraging an OIDC provider.
def odic_role_for_sa(
    config: CloudConfig,
    cluster: eks.Cluster,
    role_name: str,
    ns_service_account: str,
) -> aws.iam.Role:
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


def create_service_account(
    config: CloudConfig,
    cluster: eks.Cluster,
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
    )


def provision_k8s(config: CloudConfig) -> None:
    """
    Provisions an AWS EKS cluster with the necessary resources.

    This function creates an EKS cluster, a worker role, a VPC, and other required resources
    for running Kubernetes workloads on AWS.

    How does autoscaling work?
    We use two-level scaling strategies. First, we install a Cluster Autoscaler to scale out or in the cluster
    nodes based on the workload. However, the Cluster Autoscaler doesn't scale the nodes based on the CPU and
    memory usage of the nodes. Instead, it scales the nodes based on the number of pending pods in the cluster.
    Second, we install a Horizontal Pod Autoscaler to scale out or in the pods based on the CPU and memory usage of
    the pods. Once the pods are scaled, the Cluster Autoscaler will scale the nodes based on the number of pending pods.

    Args:
        config (CloudConfig): The cluster config provided by user.

    Returns:
        None
    """
    project = config.cluster.name

    managed_policy_arns = [
        "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
        "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
        "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    ]
    assume_role_policy = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                actions=["sts:AssumeRole"],
                effect="Allow",
                principals=[
                    aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                        type="Service",
                        identifiers=["ec2.amazonaws.com"],
                    ),
                ],
            ),
        ],
    ).json

    worker_role = aws.iam.Role(
        f"{project}-eks-worker-role",
        assume_role_policy=assume_role_policy,
        managed_policy_arns=managed_policy_arns,
    )

    # Create a VPC for our cluster
    vpc = awsx.ec2.Vpc(
        f"{project}-vpc",
        subnet_strategy=awsx.ec2.SubnetAllocationStrategy.AUTO,
        # AWS needs these tags for creating load balancers
        # See https://repost.aws/knowledge-center/eks-vpc-subnet-discovery
        subnet_specs=[
            {
                "type": awsx.ec2.SubnetType.PUBLIC,
                "tags": {"kubernetes.io/role/elb": "1"},
            },
            {
                "type": awsx.ec2.SubnetType.PRIVATE,
                "tags": {"kubernetes.io/role/internal-elb": "1"},
            },
        ],
        opts=pulumi.ResourceOptions(transformations=[_ignore_tags_transformation]),
    )

    cluster = eks.Cluster(
        project,
        vpc_id=vpc.vpc_id,
        public_subnet_ids=vpc.public_subnet_ids,
        private_subnet_ids=vpc.private_subnet_ids,
        node_associate_public_ip_address=False,
        create_oidc_provider=True,
        skip_default_node_group=True,
        # Use the worker role we created above. This is required for creating the managed node group.
        instance_roles=[worker_role],
    )

    # Create a managed node group for our cluster
    eks.ManagedNodeGroup(
        f"{project}-default-group",
        node_group_name=f"{project}-default-group",
        cluster=cluster,
        instance_types=["t2.micro"],
        scaling_config=aws.eks.NodeGroupScalingConfigArgs(
            # Each t2.micro node is bounded to a maximum 4 pods.
            # At least 2 t2.micro nodes are required for the Cluster Autoscaler to work
            desired_size=2,
            min_size=2,
            max_size=3,
        ),
        labels={"size": "t2.micro", "group": "default"},
        node_role_arn=worker_role.arn,
        subnet_ids=vpc.private_subnet_ids,
    )

    # Create a managed node group for each model group
    create_node_group_for_model_group(config, cluster, vpc, worker_role)

    k8s_provider = k8s.Provider("k8s-provider", kubeconfig=cluster.kubeconfig)

    # Deploy the metrics server. This is required for the Horizontal Pod Autoscaler to work.
    # HPA requires metrics to be available in order to scale the pods.
    k8s.yaml.ConfigFile(
        "metrics-server",
        file="https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml",
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    # Deploy the cluster autoscaler through Helm
    setup_cluster_autoscaler(
        config,
        cluster,
        k8s_provider,
    )

    aws.s3.Bucket(config.cluster.name)
    create_service_account(config, cluster)

    # Export the cluster's kubeconfig
    pulumi.export("kubeconfig", cluster.kubeconfig)


def setup_cluster_autoscaler(
    config: CloudConfig,
    cluster: eks.Cluster,
    k8s_provider: k8s.Provider,
) -> None:
    """
    Sets up the cluster autoscaler for an EKS cluster.

    Args:
        cluster (eks.Cluster): The EKS cluster.
        k8s_provider (k8s.Provider): The Kubernetes provider.
        config (CloudConfig): The cluster config provided by user.

    Returns:
        None
    """
    project = config.cluster.name

    autoscaler_policy_doc = aws.iam.get_policy_document(
        statements=[
            aws.iam.GetPolicyDocumentStatementArgs(
                actions=[
                    "autoscaling:DescribeAutoScalingGroups",
                    "autoscaling:DescribeAutoScalingInstances",
                    "autoscaling:DescribeLaunchConfigurations",
                    "autoscaling:DescribeTags",
                    "autoscaling:SetDesiredCapacity",
                    "autoscaling:TerminateInstanceInAutoScalingGroup",
                    "ec2:DescribeLaunchTemplateVersions",
                    "eks:DescribeNodegroup",
                ],
                resources=["*"],
            )
        ]
    )

    autoscaler_policy = aws.iam.Policy(
        f"{project}-autoscaler-policy", policy=autoscaler_policy_doc.json
    )

    # The OIDC provider is required because the cluster autoscaler runs within the Kubernetes
    # cluster and needs to interact with the AWS API to manage the Auto Scaling Groups (ASGs).
    # OIDC provides a secure mechanism for the cluster autoscaler to authenticate with the AWS API.
    autoscaler_role = odic_role_for_sa(
        config, cluster, "autoscaler", "kube-system:cluster-autoscaler"
    )

    aws.iam.RolePolicyAttachment(
        f"{project}-autoscaler-role-policy-attachment",
        policy_arn=autoscaler_policy.arn,
        role=autoscaler_role.name,
    )

    helm.Chart(
        "cluster-autoscaler",
        helm.ChartOpts(
            chart="cluster-autoscaler",
            version="9.34.0",
            namespace="kube-system",
            fetch_opts=helm.FetchOpts(repo="https://kubernetes.github.io/autoscaler"),
            values={
                "autoDiscovery": {"clusterName": cluster.eks_cluster.name},
                "awsRegion": aws.config.region,
                "rbac": {
                    "create": True,
                    "serviceAccount": {
                        "create": True,
                        "name": "cluster-autoscaler",
                        "annotations": {
                            "eks.amazonaws.com/role-arn": autoscaler_role.arn
                        },
                    },
                },
                "serviceMonitor": {"interval": "2s"},
                "image": {"tag": "v1.28.2"},
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

from typing import Optional

import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
import pulumi_eks as eks
import pulumi_kubernetes as k8s

from light.cluster.aws.cloudwatch import enable_cloudwatch
from light.cluster.aws.cluster_autoscaler import create_cluster_autoscaler
from light.cluster.aws.ebs_csi_driver import create_ebs_csi_driver
from light.cluster.aws.service_account import create_service_accounts
from light.cluster.keda import create_keda
from light.cluster.knative import create_knative
from light.cluster.qdrant import create_qdrant
from light.cluster.redis import create_redis
from light.config import CloudConfig
from light.utils import kubify_name, save_kubeconfig


def _ignore_tags_transformation(
    args: pulumi.ResourceTransformationArgs,
) -> Optional[pulumi.ResourceTransformationResult]:
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
    """
    Creates a managed node group for each model group in the provided configuration.

    This function iterates over the model groups in the configuration. For each
    model group, it creates a managed node group in the provided EKS cluster.
    The node group is configured with the instance type, scaling configuration,
    labels, and taints specified in the model group.

    Args:
        config (CloudConfig): The cloud configuration containing the model groups.
        cluster (eks.Cluster): The EKS cluster to create the node groups in.
        vpc (awsx.ec2.Vpc): The VPC to associate the node groups with.
        worker_role (aws.iam.Role): The IAM role for the worker nodes.

    Returns:
        None
    """
    if config.modelGroups is None:
        return

    project = config.cluster.name

    for model_group in config.modelGroups:
        # Create a managed node group for our cluster
        eks.ManagedNodeGroup(
            f"{project}-{kubify_name(model_group.name)}-group",
            node_group_name=f"{project}-{kubify_name(model_group.name)}-group",
            cluster=cluster,
            instance_types=[model_group.nodeType],
            # Set the desired size of the node group to the minimum number of instances
            # specified for the model group.
            # Note: Scaling down to 0 is not supported, since cold starting time is
            # too long for model group services.
            scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                desired_size=model_group.minInstances,
                min_size=model_group.minInstances,
                max_size=model_group.maxInstances,
            ),
            labels={
                "size": model_group.nodeType,
                "app": "model-group",
                "model": model_group.name,
            },
            node_role_arn=worker_role.arn,
            subnet_ids=vpc.private_subnet_ids,
            # Apply taints to ensure that only pods belonging to the same model group
            # can be scheduled on this node group.
            taints=[
                aws.eks.NodeGroupTaintArgs(
                    effect="NO_SCHEDULE", key="app", value="model-group"
                ),
                aws.eks.NodeGroupTaintArgs(
                    effect="NO_SCHEDULE", key="model", value=model_group.name
                ),
            ],
        )


def create_node_group_for_qdrant(
    config: CloudConfig,
    cluster: eks.Cluster,
    vpc: awsx.ec2.Vpc,
    worker_role: aws.iam.Role,
) -> None:
    """
    Creates a managed node group for Qdrant in the provided EKS cluster.

    This function creates a managed node group in the EKS cluster with the
    instance type and replicas specified in the vectorStore configuration.
    The node group is labeled with the instance type and the app name ("qdrant").
    It uses the provided worker role and is associated with the private subnets
    of the provided VPC. A taint is applied to ensure that only pods with a
    toleration for "app=qdrant" can be scheduled on this node group.

    If the vectorStore configuration is not provided, the function returns without
    creating a node group.

    Args:
        config (CloudConfig): The cloud configuration containing the vectorStore
            configuration.
        cluster (eks.Cluster): The EKS cluster to create the node group in.
        vpc (awsx.ec2.Vpc): The VPC to associate the node group with.
        worker_role (aws.iam.Role): The IAM role for the worker nodes.

    Returns:
        None
    """
    if config.vectorStore is None:
        return

    project = config.cluster.name

    vectorStore = config.vectorStore

    # Create a managed node group for our cluster
    eks.ManagedNodeGroup(
        f"{project}-qdrant-group",
        node_group_name=f"{project}-qdrant-group",
        cluster=cluster,
        instance_types=[vectorStore.nodeType],
        # Scaling down to 0 is not supported
        scaling_config=aws.eks.NodeGroupScalingConfigArgs(
            desired_size=vectorStore.replicas,
            min_size=vectorStore.replicas,
            max_size=vectorStore.replicas,
        ),
        labels={
            "size": vectorStore.nodeType,
            "app": "qdrant",
        },
        node_role_arn=worker_role.arn,
        subnet_ids=vpc.private_subnet_ids,
        taints=[
            aws.eks.NodeGroupTaintArgs(effect="NO_SCHEDULE", key="app", value="qdrant"),
        ],
    )


def create_k8s_cluster(config: CloudConfig) -> eks.Cluster:
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
        instance_types=[config.cluster.nodeType],
        scaling_config=aws.eks.NodeGroupScalingConfigArgs(
            desired_size=config.cluster.minNodes,
            min_size=config.cluster.minNodes,
            max_size=config.cluster.maxNodes,
        ),
        labels={"size": config.cluster.nodeType, "group": "default"},
        node_role_arn=worker_role.arn,
        subnet_ids=vpc.private_subnet_ids,
    )

    # Create a managed node group for each model group
    create_node_group_for_model_group(config, cluster, vpc, worker_role)

    # Create a managed node group for Qdrant
    create_node_group_for_qdrant(config, cluster, vpc, worker_role)

    k8s_provider = k8s.Provider("k8s-provider", kubeconfig=cluster.kubeconfig)

    # Deploy the metrics server. This is required for the Horizontal Pod Autoscaler to work.
    # HPA requires metrics to be available in order to scale the pods.
    k8s.yaml.ConfigFile(
        "metrics-server",
        file="https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml",
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    # Deploy the cluster autoscaler through Helm
    create_cluster_autoscaler(
        config,
        cluster,
        k8s_provider,
    )

    create_ebs_csi_driver(config, cluster, k8s_provider)
    create_redis(k8s_provider)
    create_keda(k8s_provider)
    create_knative(k8s_provider)
    create_qdrant(config, k8s_provider)

    create_service_accounts(config, cluster, k8s_provider)
    enable_cloudwatch(config, k8s_provider)

    # Save the kubeconfig to a file
    cluster.kubeconfig_json.apply(
        lambda kubeconfig_json: save_kubeconfig(config.cluster.name, kubeconfig_json)
    )

    return cluster

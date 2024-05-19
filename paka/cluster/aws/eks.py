from __future__ import annotations

import json
from typing import List, Optional, cast

import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
import pulumi_eks as eks
import pulumi_kubernetes as k8s

from paka.cluster.aws.cloudwatch import enable_cloudwatch
from paka.cluster.aws.cluster_autoscaler import create_cluster_autoscaler
from paka.cluster.aws.ebs_csi_driver import create_ebs_csi_driver
from paka.cluster.aws.elb import update_elb_idle_timeout
from paka.cluster.aws.service_account import create_service_accounts
from paka.cluster.context import Context
from paka.cluster.keda import create_keda
from paka.cluster.knative import create_knative_and_istio
from paka.cluster.namespace import create_namespace
from paka.cluster.nvidia_device_plugin import install_nvidia_device_plugin
from paka.cluster.prometheus import create_prometheus
from paka.cluster.qdrant import create_qdrant
from paka.cluster.redis import create_redis
from paka.cluster.zipkin import create_zipkin
from paka.config import AwsMixedModelGroup, AwsModelGroup
from paka.k8s.utils import update_kubeconfig
from paka.utils import kubify_name


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
    ctx: Context,
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
    if ctx.cloud_config.modelGroups is None:
        return

    cluster_name = ctx.cluster_name

    model_groups = cast(List[AwsModelGroup], ctx.cloud_config.modelGroups)

    for model_group in model_groups:
        taints = [
            aws.eks.NodeGroupTaintArgs(
                effect="NO_SCHEDULE", key="app", value="model-group"
            ),
            aws.eks.NodeGroupTaintArgs(
                effect="NO_SCHEDULE", key="model", value=model_group.name
            ),
        ]

        gpu_enabled = model_group.gpu and model_group.gpu.enabled

        ami_type = "AL2_x86_64_GPU" if gpu_enabled else None

        disk_size = (
            model_group.gpu.diskSize
            if gpu_enabled and model_group.gpu
            else model_group.diskSize
        )

        # Create a managed node group for our cluster
        eks.ManagedNodeGroup(
            f"{cluster_name}-{kubify_name(model_group.name)}-group",
            node_group_name=f"{cluster_name}-{kubify_name(model_group.name)}-on-demand",
            cluster=cluster,
            instance_types=[model_group.nodeType],
            scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                desired_size=model_group.minInstances,
                min_size=model_group.minInstances,
                max_size=model_group.maxInstances,
            ),
            labels={
                "size": model_group.nodeType,
                "app": "model-group",
                "model": model_group.name,
                "lifecycle": "on-demand",
            },
            node_role_arn=worker_role.arn,
            subnet_ids=vpc.private_subnet_ids,
            taints=taints,
            # Supported AMI types https://docs.aws.amazon.com/eks/latest/APIReference/API_Nodegroup.html#AmazonEKS-Type-Nodegroup-amiType
            ami_type=ami_type,
            disk_size=disk_size,
            capacity_type="ON_DEMAND",
        )


def create_node_group_for_mixed_model_group(
    ctx: Context,
    cluster: eks.Cluster,
    vpc: awsx.ec2.Vpc,
    worker_role: aws.iam.Role,
) -> None:

    if ctx.cloud_config.mixedModelGroups is None:
        return

    cluster_name = ctx.cluster_name

    mixed_model_groups = cast(
        List[AwsMixedModelGroup], ctx.cloud_config.mixedModelGroups
    )

    for mixed_model_group in mixed_model_groups:
        taints = [
            aws.eks.NodeGroupTaintArgs(
                effect="NO_SCHEDULE", key="app", value="model-group"
            ),
            aws.eks.NodeGroupTaintArgs(
                effect="NO_SCHEDULE", key="model", value=mixed_model_group.name
            ),
        ]

        gpu_enabled = mixed_model_group.gpu and mixed_model_group.gpu.enabled

        ami_type = "AL2_x86_64_GPU" if gpu_enabled else None

        disk_size = (
            mixed_model_group.gpu.diskSize
            if gpu_enabled and mixed_model_group.gpu
            else mixed_model_group.diskSize
        )

        # Create a managed node group for our cluster
        eks.ManagedNodeGroup(
            f"{cluster_name}-{kubify_name(mixed_model_group.name)}-group",
            node_group_name=f"{cluster_name}-{kubify_name(mixed_model_group.name)}-on-demand",
            cluster=cluster,
            instance_types=[mixed_model_group.nodeType],
            scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                desired_size=mixed_model_group.baseInstances,
                min_size=mixed_model_group.baseInstances,
                max_size=mixed_model_group.maxOnDemandInstances,
            ),
            labels={
                "size": mixed_model_group.nodeType,
                "app": "model-group",
                "model": mixed_model_group.name,
                "lifecycle": "on-demand",
            },
            node_role_arn=worker_role.arn,
            subnet_ids=vpc.private_subnet_ids,
            taints=taints,
            # Supported AMI types https://docs.aws.amazon.com/eks/latest/APIReference/API_Nodegroup.html#AmazonEKS-Type-Nodegroup-amiType
            ami_type=ami_type,
            disk_size=disk_size,
            capacity_type="ON_DEMAND",
        )

        # Create a managed node group with spot instances
        eks.ManagedNodeGroup(
            f"{cluster_name}-{kubify_name(mixed_model_group.name)}-spot-group",
            node_group_name=f"{cluster_name}-{kubify_name(mixed_model_group.name)}-spot",
            cluster=cluster,
            instance_types=[mixed_model_group.nodeType],
            scaling_config=aws.eks.NodeGroupScalingConfigArgs(
                desired_size=mixed_model_group.spot.minInstances,
                min_size=mixed_model_group.spot.minInstances,
                max_size=mixed_model_group.spot.maxInstances,
            ),
            labels={
                "size": mixed_model_group.nodeType,
                "app": "model-group",
                "model": mixed_model_group.name,
                "lifecycle": "spot",
            },
            node_role_arn=worker_role.arn,
            subnet_ids=vpc.private_subnet_ids,
            taints=taints,
            # Supported AMI types https://docs.aws.amazon.com/eks/latest/APIReference/API_Nodegroup.html#AmazonEKS-Type-Nodegroup-amiType
            ami_type=ami_type,
            disk_size=disk_size,
            capacity_type="SPOT",
        )


def create_node_group_for_qdrant(
    ctx: Context,
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
    if ctx.cloud_config.vectorStore is None:
        return

    cluster_name = ctx.cluster_name

    vectorStore = ctx.cloud_config.vectorStore

    # Create a managed node group for our cluster
    eks.ManagedNodeGroup(
        f"{cluster_name}-qdrant-group",
        node_group_name=f"{cluster_name}-qdrant-group",
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


def create_k8s_cluster(ctx: Context) -> eks.Cluster:
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

    Returns:
        eks.Cluster
    """
    cluster_name = ctx.cluster_name

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
        f"{cluster_name}-eks-worker-role",
        assume_role_policy=assume_role_policy,
        managed_policy_arns=managed_policy_arns,
    )

    # Create a VPC for our cluster
    vpc = awsx.ec2.Vpc(
        f"{cluster_name}-vpc",
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
        cluster_name,
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
        f"{cluster_name}-default-group",
        node_group_name=f"{cluster_name}-default-group",
        cluster=cluster,
        instance_types=[ctx.cloud_config.cluster.nodeType],
        scaling_config=aws.eks.NodeGroupScalingConfigArgs(
            desired_size=ctx.cloud_config.cluster.minNodes,
            min_size=ctx.cloud_config.cluster.minNodes,
            max_size=ctx.cloud_config.cluster.maxNodes,
        ),
        labels={"size": ctx.cloud_config.cluster.nodeType, "group": "default"},
        node_role_arn=worker_role.arn,
        subnet_ids=vpc.private_subnet_ids,
    )

    # Create a managed node group for each model group
    create_node_group_for_model_group(ctx, cluster, vpc, worker_role)

    create_node_group_for_mixed_model_group(ctx, cluster, vpc, worker_role)

    # Create a managed node group for Qdrant
    create_node_group_for_qdrant(ctx, cluster, vpc, worker_role)

    def create_eks_resources(kubeconfig_json: str) -> None:
        k8s_provider = k8s.Provider("k8s-provider", kubeconfig=cluster.kubeconfig)
        ctx.set_k8s_provider(k8s_provider)
        ctx.set_kubeconfig(kubeconfig_json)

        if ctx.should_save_kubeconfig:
            update_kubeconfig(json.loads(kubeconfig_json))

        # Deploy the metrics server. This is required for the Horizontal Pod Autoscaler to work.
        # HPA requires metrics to be available in order to scale the pods.
        k8s.yaml.ConfigFile(
            "metrics-server",
            file="https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml",
            opts=pulumi.ResourceOptions(provider=k8s_provider),
        )

        # Deploy the cluster autoscaler through Helm
        create_cluster_autoscaler(
            ctx,
            cluster,
        )

        create_ebs_csi_driver(ctx, cluster)
        create_namespace(ctx, kubeconfig_json)
        # TODO: Decouple knative and istio
        create_knative_and_istio(ctx)
        create_redis(ctx)
        create_keda(ctx)
        create_qdrant(ctx)

        create_service_accounts(ctx, cluster)
        enable_cloudwatch(ctx)
        create_prometheus(ctx)
        create_zipkin(ctx)
        # Install the NVIDIA device plugin for GPU support
        # Even if the cluster doesn't have GPUs, this won't cause any issues
        install_nvidia_device_plugin(ctx)

        # TODO: Set timeout to be the one used by knative
        update_elb_idle_timeout(kubeconfig_json, 300)

    # Save the kubeconfig to a file
    cluster.kubeconfig_json.apply(create_eks_resources)

    return cluster

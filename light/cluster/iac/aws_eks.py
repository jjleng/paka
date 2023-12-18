import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
import pulumi_eks as eks
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm


def ignore_tags(
    args: pulumi.ResourceTransformationArgs,
) -> pulumi.ResourceTransformationResult | None:
    if args.type_ == "aws:ec2/vpc:Vpc" or args.type_ == "aws:ec2/subnet:Subnet":
        return pulumi.ResourceTransformationResult(
            props=args.props,
            opts=pulumi.ResourceOptions.merge(
                args.opts, pulumi.ResourceOptions(ignore_changes=["tags"])
            ),
        )
    return None


def provision_k8s() -> None:
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

    role = aws.iam.Role(
        "eks-worker-role",
        assume_role_policy=assume_role_policy,
        managed_policy_arns=managed_policy_arns,
    )

    # Create a VPC for our cluster
    vpc = awsx.ec2.Vpc(
        "vpc",
        subnet_strategy=awsx.ec2.SubnetAllocationStrategy.AUTO,
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
        opts=pulumi.ResourceOptions(transformations=[ignore_tags]),
    )

    cluster = eks.Cluster(
        "cluster",
        vpc_id=vpc.vpc_id,
        public_subnet_ids=vpc.public_subnet_ids,
        private_subnet_ids=vpc.private_subnet_ids,
        node_associate_public_ip_address=False,
        create_oidc_provider=True,
        skip_default_node_group=True,
        instance_roles=[role],
    )

    eks.ManagedNodeGroup(
        "micro-group",
        node_group_name="micro-group",
        cluster=cluster,
        instance_types=["t2.micro"],
        scaling_config=aws.eks.NodeGroupScalingConfigArgs(
            desired_size=2,
            min_size=1,
            max_size=4,
        ),
        labels={"ondemand": "true", "size": "micro"},
        node_role_arn=role.arn,
        subnet_ids=vpc.private_subnet_ids,
    )

    k8s_provider = k8s.Provider("k8s-provider", kubeconfig=cluster.kubeconfig)

    k8s.yaml.ConfigFile(
        "metrics-server",
        file="https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml",
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    setup_cluster_autoscaler(cluster, k8s_provider)

    # Export the cluster's kubeconfig
    pulumi.export("kubeconfig", cluster.kubeconfig)


def setup_cluster_autoscaler(cluster: eks.Cluster, k8s_provider: k8s.Provider) -> None:
    # IAM Policy Document for Cluster Autoscaler
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

    # Create IAM Policy
    autoscaler_policy = aws.iam.Policy(
        "autoscaler-policy", policy=autoscaler_policy_doc.json
    )

    # Fetch the OIDC provider URL and the thumbprint from the EKS cluster
    oidc_provider_url = cluster.core.oidc_provider.url
    oidc_provider = aws.iam.get_open_id_connect_provider(
        url=oidc_provider_url.apply(lambda url: "https://" + url if url else "")
    )

    # Update the IAM Role for Cluster Autoscaler with the correct trust relationship
    autoscaler_role = aws.iam.Role(
        "autoscaler-role",
        assume_role_policy=oidc_provider_url.apply(
            lambda url: aws.iam.get_policy_document(
                statements=[
                    aws.iam.GetPolicyDocumentStatementArgs(
                        actions=["sts:AssumeRoleWithWebIdentity"],
                        effect="Allow",
                        principals=[
                            aws.iam.GetPolicyDocumentStatementPrincipalArgs(
                                type="Federated",
                                identifiers=[oidc_provider.arn],
                            )
                        ],
                        conditions=[
                            aws.iam.GetPolicyDocumentStatementConditionArgs(
                                test="StringEquals",
                                variable=f"{url}:sub",
                                values=[
                                    "system:serviceaccount:kube-system:cluster-autoscaler"
                                ],
                            )
                        ],
                    )
                ],
            ).json
        ),
    )

    # Attach policy to the role
    aws.iam.RolePolicyAttachment(
        "autoscaler-role-policy-attachment",
        policy_arn=autoscaler_policy.arn,
        role=autoscaler_role.name,
    )

    # Helm chart for Cluster Autoscaler
    helm.Chart(
        "cluster-autoscaler",
        helm.ChartOpts(
            chart="cluster-autoscaler",
            version="9.34.0",  # Use the appropriate version
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
                "image": {"tag": "v1.28.2"},  # Use the appropriate tag
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

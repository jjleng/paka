import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
import pulumi_eks as eks
import json
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm
import datetime
from typing import Any


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
    assume_role_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ec2.amazonaws.com",
                    },
                }
            ],
        }
    )
    role = aws.iam.Role(
        "eks-worker-role",
        assume_role_policy=assume_role_policy,
        managed_policy_arns=managed_policy_arns,
    )

    instance_profile = aws.iam.InstanceProfile("instanceProfile", role=role.name)

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

    # Node Group with micro instances
    # eks.NodeGroupV2(
    #     "micro-group",
    #     cluster=cluster,
    #     instance_type="t2.micro",
    #     desired_capacity=1,
    #     min_size=1,
    #     max_size=3,
    #     spot_price="1",
    #     labels={"ondemand": "true", "size": "micro"},
    #     instance_profile=instance_profile,
    #     node_associate_public_ip_address=False,
    #     node_subnet_ids=vpc.private_subnet_ids,
    # )

    k8s_provider = k8s.Provider("k8s-provider", kubeconfig=cluster.kubeconfig)

    def add_insecure_tls_arg(obj: [Any], _opts: pulumi.ResourceOptions) -> None:
        if obj["kind"] == "Deployment" and "metrics-server" in obj["metadata"]["name"]:
            containers = obj["spec"]["template"]["spec"]["containers"]
            if len(containers) > 0:
                # Ensure 'args' key exists
                if "args" not in containers[0]:
                    containers[0]["args"] = []
                # Add the --kubelet-insecure-tls flag
                containers[0]["args"].append("--kubelet-insecure-tls")

    metrics_server_config = k8s.yaml.ConfigFile(
        "metrics-server",
        file="https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml",
        transformations=[add_insecure_tls_arg],
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    setup_cluster_autoscaler(cluster, k8s_provider)
    deploy_nginx(k8s_provider)
    deploy_cpu_load_generator(k8s_provider)

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
            lambda url: json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Federated": f"{oidc_provider.arn}"},
                            "Action": "sts:AssumeRoleWithWebIdentity",
                            "Condition": {
                                "StringEquals": {
                                    f"{url}:sub": "system:serviceaccount:kube-system:cluster-autoscaler"
                                }
                            },
                        }
                    ],
                }
            )
        ),
    )

    # Attach policy to the role
    aws.iam.RolePolicyAttachment(
        "autoscaler-role-policy-attachment",
        policy_arn=autoscaler_policy.arn,
        role=autoscaler_role.name,
    )

    # Helm chart for Cluster Autoscaler
    autoscaler_chart = helm.Chart(
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
                "image": {"tag": "v1.28.2"},  # Use the appropriate tag
            },
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )


def deploy_nginx(k8s_provider: k8s.Provider) -> None:
    app_labels = {"app": "nginx"}
    deployment = k8s.apps.v1.Deployment(
        "nginx-deployment",
        spec={
            "selector": {"matchLabels": app_labels},
            "replicas": 1,
            "template": {
                "metadata": {"labels": app_labels},
                "spec": {
                    "containers": [
                        {
                            "name": "nginx",
                            "image": "nginx:1.15.4",
                            "resources": {
                                "requests": {"cpu": "100m"},
                            },
                            "ports": [{"containerPort": 80}],
                        }
                    ]
                },
            },
        },
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    # hpa = k8s.autoscaling.v1.HorizontalPodAutoscaler(
    #     "nginx-hpa",
    #     spec={
    #         "scaleTargetRef": {
    #             "apiVersion": "apps/v1",
    #             "kind": "Deployment",
    #             "name": deployment.metadata["name"],
    #         },
    #         "minReplicas": 1,
    #         "maxReplicas": 3,
    #         "targetCPUUtilizationPercentage": 50,
    #     },
    #     opts=pulumi.ResourceOptions(provider=k8s_provider),
    # )


def deploy_cpu_load_generator(k8s_provider: k8s.Provider) -> None:
    app_labels = {"app": "cpu-load-generator"}

    force_update_annotation = str(datetime.datetime.now())

    deployment = k8s.apps.v1.Deployment(
        "cpu-load-generator",
        spec=k8s.apps.v1.DeploymentSpecArgs(
            selector=k8s.meta.v1.LabelSelectorArgs(match_labels=app_labels),
            replicas=1,
            template=k8s.core.v1.PodTemplateSpecArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    labels=app_labels,
                    annotations={"force-update-timestamp": force_update_annotation},
                ),
                spec=k8s.core.v1.PodSpecArgs(
                    node_selector={
                        "ondemand": "true",
                        "size": "micro",
                    },  # Node selector added here
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            name="busybox",
                            image="busybox",
                            args=[
                                "/bin/sh",
                                "-c",
                                "while true; do md5sum /dev/zero; done",
                            ],
                            resources=k8s.core.v1.ResourceRequirementsArgs(
                                requests={"cpu": "100m"}, limits={"cpu": "500m"}
                            ),
                        )
                    ],
                ),
            ),
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

    hpa = k8s.autoscaling.v1.HorizontalPodAutoscaler(
        "cpu-load-generator-hpa",
        spec=k8s.autoscaling.v1.HorizontalPodAutoscalerSpecArgs(
            scale_target_ref=k8s.autoscaling.v1.CrossVersionObjectReferenceArgs(
                api_version="apps/v1", kind="Deployment", name=deployment.metadata.name
            ),
            min_replicas=1,
            max_replicas=4,
            target_cpu_utilization_percentage=50,
        ),
        opts=pulumi.ResourceOptions(provider=k8s_provider),
    )

from kubernetes import client
from light.k8s import create_namespace, apply_resource
from light.config import CloudConfig


def create_celery_workers(config: CloudConfig) -> None:
    project = config.cluster.name

    api = client.CoreV1Api()

    # Create a namespace
    create_namespace(project, "celery-workers")

    # Create a service account
    service_account = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            name="celery-worker-sa", namespace="celery-workers"
        )
    )
    apply_resource(project, service_account)

    # Create a Kubernetes RoleBinding that authorizes the service account to read the Redis secret
    role_binding = client.V1RoleBinding(
        # RoleBinding should be created in the same namespace as the role, 'redis'
        metadata=client.V1ObjectMeta(name="redis-secret-reader", namespace="redis"),
        subjects=[
            client.V1Subject(
                kind="ServiceAccount",
                name="celery-worker-sa",
                namespace="celery-workers",
            )
        ],
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io",
            kind="Role",
            name="redis-secret-reader",
        ),
    )
    apply_resource(project, role_binding)

    config_map = client.V1ConfigMap(
        metadata=client.V1ObjectMeta(
            name="celery-workers-config", namespace="celery-workers"
        ),
        data={
            "redis-host": "redis-master.redis.svc.cluster.local",
        },
    )
    apply_resource(project, config_map)

    # Create a deployment
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(name="celery-worker", namespace="celery-workers"),
        spec=client.V1DeploymentSpec(
            replicas=0,
            selector=client.V1LabelSelector(match_labels={"name": "celery-worker"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"name": "celery-worker"}),
                spec=client.V1PodSpec(
                    service_account_name="celery-worker-sa",
                    containers=[
                        client.V1Container(
                            name="celery-worker",
                            image="user/light-celery-worker:latest",
                            env=[
                                client.V1EnvVar(
                                    name="REDIS_HOST",
                                    value_from=client.V1EnvVarSource(
                                        config_map_key_ref=client.V1ConfigMapKeySelector(
                                            name="celery-workers-config",
                                            key="redis-host",
                                        ),
                                    ),
                                ),
                                client.V1EnvVar(
                                    name="REDIS_PASSWORD",
                                    value_from=client.V1EnvVarSource(
                                        secret_key_ref=client.V1SecretKeySelector(
                                            name="redis-password",
                                            key="password",
                                        ),
                                    ),
                                ),
                            ],
                        )
                    ],
                ),
            ),
        ),
    )
    api = client.AppsV1Api()
    api.create_namespaced_deployment("celery-workers", body=deployment)

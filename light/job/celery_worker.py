import shlex

from kubernetes import client

from light.constants import CELERY_WORKER_SA, JOB_NS
from light.job.autoscaler import create_autoscaler
from light.k8s import apply_resource, create_namespace, create_service_account


def create_deployment(
    runtime_command: str,
    namespace: str,
    deployment_name: str,
    service_account_name: str,
    image_name: str,
) -> None:
    containers = [
        client.V1Container(
            name="celery-worker",
            image=image_name,
            command=shlex.split(runtime_command),
            env=[
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
        ),
    ]

    deployment = client.V1Deployment(
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=deployment_name, namespace=namespace),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"name": deployment_name}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"name": deployment_name}),
                spec=client.V1PodSpec(
                    service_account_name=service_account_name,
                    containers=containers,
                ),
            ),
        ),
    )
    apply_resource(deployment)


def create_celery_workers(
    runtime_command: str,
    task_name: str,
    image: str,
    drain_existing_task: bool = True,
) -> None:
    namespace = JOB_NS
    service_account_name = CELERY_WORKER_SA

    # Create the namespace and service account for celery workers
    create_namespace(namespace)
    create_service_account(namespace, service_account_name)

    deployment_name = task_name

    create_deployment(
        runtime_command,
        namespace,
        deployment_name,
        service_account_name,
        image,
    )

    create_autoscaler(
        namespace=namespace,
        redis_svc_name="redis-master",
        queue_name="0",
        trigger_queue_length=5,
        deployment_name=deployment_name,
        min_replicas=1,
        max_replicas=5,
    )

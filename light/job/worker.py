import shlex
import time

from kubernetes import client

from light.constants import ACCESS_ALL_SA, APP_NS
from light.job.autoscaler import create_autoscaler, delete_autoscaler
from light.k8s import apply_resource, create_namespace, try_load_kubeconfig
from light.logger import logger

try_load_kubeconfig()


def wait_for_pods_to_drain(namespace: str, deployment_name: str) -> None:
    while True:
        pods = client.CoreV1Api().list_namespaced_pod(
            namespace, label_selector=f"app={deployment_name},role=worker"
        )
        if not pods.items:
            break
        logger.info(f"Waiting for {len(pods.items)} pod(s) to drain...")
        time.sleep(10)


# k8s job is another option to run a task. We are using k8s deployment here.
# The advantage of using k8s deployment is that we retrigger the workers without creating a new deployment.
def create_deployment(
    runtime_command: str,
    namespace: str,
    deployment_name: str,
    service_account_name: str,
    image_name: str,
) -> None:
    containers = [
        client.V1Container(
            name="worker",
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
            replicas=0,
            selector=client.V1LabelSelector(
                match_labels={"app": deployment_name, "role": "worker"}
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={"app": deployment_name, "role": "worker"}
                ),
                spec=client.V1PodSpec(
                    service_account_name=service_account_name,
                    containers=containers,
                ),
            ),
        ),
    )
    apply_resource(deployment)


def create_workers(
    runtime_command: str,
    task_name: str,
    image: str,
    tasks_per_worker: int = 5,
    max_replicas: int = 5,
    drain_existing_task: bool = True,
) -> None:
    namespace = APP_NS

    create_namespace(namespace)

    deployment_name = task_name

    if drain_existing_task:
        # Check if the deployment already exists
        # Wait for pods to drain
        wait_for_pods_to_drain(namespace, deployment_name)

    # Otherwise, upsert the deployment. This will update the deployment if it already exists.
    create_deployment(
        runtime_command,
        namespace,
        deployment_name,
        ACCESS_ALL_SA,
        image,
    )

    create_autoscaler(
        namespace=namespace,
        redis_svc_name="redis-master",
        queue_name="0",
        trigger_queue_length=tasks_per_worker,
        job_name=deployment_name,
        min_replicas=0,  # Hard coded, scale to 0
        max_replicas=max_replicas,
    )


def delete_workers(
    job_name: str,
    drain_existing_task: bool = True,
) -> None:
    namespace = APP_NS

    if drain_existing_task:
        wait_for_pods_to_drain(namespace, job_name)

    delete_autoscaler(namespace, job_name)

    client.AppsV1Api().delete_namespaced_deployment(job_name, namespace)

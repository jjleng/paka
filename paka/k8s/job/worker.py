import shlex
import time

from kubernetes import client

from paka.constants import ACCESS_ALL_SA
from paka.k8s.job.autoscaler import create_autoscaler, delete_autoscaler
from paka.k8s.utils import apply_resource, create_namespace
from paka.logger import logger


def wait_for_pods_to_drain(namespace: str, deployment_name: str) -> None:
    """
    Waits for all worker pods of a specific deployment in a namespace to drain.

    This function continuously checks for the existence of worker pods associated with a specific deployment
    in a given namespace. If any such pods exist, the function waits for 10 seconds before checking again.
    The function returns when no such pods exist.

    Args:
        namespace (str): The namespace in which to check for pods.
        deployment_name (str): The name of the deployment whose pods to wait for.

    Returns:
        None
    """
    while True:
        pods = client.CoreV1Api().list_namespaced_pod(
            namespace,
            label_selector=f"app={deployment_name},role=worker",
        )
        if not pods.items:
            break
        logger.info(f"Waiting for {len(pods.items)} pod(s) to drain...")
        time.sleep(10)


# While Kubernetes Jobs are an option for running tasks, we opt for
# Kubernetes Deployments in this case. The benefit of using Deployments is
# that they allow us to restart the workers without the need to create a new
# deployment.
def create_deployment(
    entrypoint: str,
    namespace: str,
    deployment_name: str,
    service_account_name: str,
    image_name: str,
) -> None:
    containers = [
        client.V1Container(
            name="worker",
            image=image_name,
            command=shlex.split(entrypoint),
            image_pull_policy="Always",
        ),
    ]

    deployment = client.V1Deployment(
        kind="Deployment",
        metadata=client.V1ObjectMeta(
            name=deployment_name,
            namespace=namespace,
            labels={
                "role": "worker",
            },
        ),
        spec=client.V1DeploymentSpec(
            replicas=0,
            selector=client.V1LabelSelector(
                match_labels={
                    "app": deployment_name,
                    "role": "worker",
                }
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={
                        "app": deployment_name,
                        "role": "worker",
                    }
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
    namespace: str,
    job_name: str,
    image: str,
    entrypoint: str,
    tasks_per_worker: int = 5,
    max_replicas: int = 5,
    drain_existing_job: bool = True,
) -> None:
    create_namespace(namespace)

    deployment_name = job_name

    if drain_existing_job:
        # Check if the deployment already exists
        # Wait for pods to drain
        wait_for_pods_to_drain(namespace, deployment_name)

    # Otherwise, upsert the deployment. This will update the deployment if it already exists.
    create_deployment(
        entrypoint,
        namespace,
        deployment_name,
        ACCESS_ALL_SA,
        image,
    )

    create_autoscaler(
        namespace=namespace,
        redis_svc_name="redis-master",
        queue_name="celery",
        trigger_queue_length=tasks_per_worker,
        job_name=deployment_name,
        min_replicas=0,  # Hard coded, scale to 0
        max_replicas=max_replicas,
    )


def delete_workers(
    namespace: str,
    job_name: str,
    drain_existing_job: bool = True,
) -> None:
    deployment_name = job_name

    if drain_existing_job:
        wait_for_pods_to_drain(namespace, deployment_name)

    delete_autoscaler(namespace, deployment_name)

    client.AppsV1Api().delete_namespaced_deployment(deployment_name, namespace)

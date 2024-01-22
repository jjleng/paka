import os
import shlex
from typing import Optional

import typer
from kubernetes import client

from light.cli.build import build
from light.constants import APP_NS
from light.k8s import tail_logs, try_load_kubeconfig
from light.logger import logger
from light.utils import kubify_name, random_str, read_current_cluster_data

CLEANUP_TIMEOUT = 600  # 10 minutes

run_app = typer.Typer()

try_load_kubeconfig()


@run_app.callback(invoke_without_command=True)
def one_off_script(
    entrypoint: str = typer.Option(
        ...,
        "--entrypoint",
        help="The entrypoint to run.",
    ),
    source_dir: Optional[str] = typer.Option(
        None,
        "--source",
        help="Source directory of the application.",
    ),
    image: Optional[str] = typer.Option(
        None,
        "--image",
        help="The name of the image to deploy.",
    ),
) -> None:
    if bool(source_dir) == bool(image):
        logger.error(
            "Exactly one of --source or --image must be provided. Please see --help for more information."
        )
        raise typer.Exit(1)

    # Generate a job name which is the hash of the command
    job_name = f"run-{kubify_name(random_str(10))}"

    if not image and source_dir:
        source_dir = os.path.abspath(os.path.expanduser(source_dir))
        image = os.path.basename(source_dir)
        build(source_dir, image)
        image = f"{image}-latest"

    registry_uri = read_current_cluster_data("registry")

    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name, labels={"job-name": job_name}),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="one-off-script",
                            image=f"{registry_uri}:{image}",
                            image_pull_policy="Always",
                            command=shlex.split(entrypoint),
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
                        )
                    ],
                    restart_policy="Never",
                )
            ),
            backoff_limit=0,
            ttl_seconds_after_finished=CLEANUP_TIMEOUT,
        ),
    )

    namespace = APP_NS

    logger.info(f"Submitting the task...")
    batch_api = client.BatchV1Api()
    batch_api.create_namespaced_job(namespace=namespace, body=job)
    logger.info(f"Successfully submitted the task.")

    logger.info(f"Waiting for the task to complete...")
    api = client.CoreV1Api()
    pods = api.list_namespaced_pod(
        namespace=namespace, label_selector=f"job-name={job_name}"
    )
    for pod in pods.items:
        tail_logs(namespace, pod.metadata.name)

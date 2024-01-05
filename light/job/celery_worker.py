import json

from kubernetes import client

from light.config import CloudConfig
from light.constants import CELERY_WORKER_SA, FISSION_CRD_NS, JOBS_NS
from light.job.autoscaler import create_autoscaler
from light.job.entrypoint import write_entrypoint_script_to_cfgmap
from light.job.utils import get_package_details
from light.k8s import (
    apply_resource,
    create_namespace,
    create_role,
    create_role_binding,
    create_service_account,
)


def create_deployment(
    runtime_command: str,
    task_name: str,
    namespace: str,
    deployment_name: str,
    service_account_name: str,
    image_name: str,
) -> None:
    package_name = task_name

    package = get_package_details(FISSION_CRD_NS, package_name)
    fetch_payload = {
        "fetchType": 1,
        "filename": task_name,
        "package": {
            "name": task_name,
            "namespace": FISSION_CRD_NS,
            "resourceVersion": package.metadata.resourceVersion,
        },
        "keeparchive": False,
    }

    write_entrypoint_script_to_cfgmap(
        namespace, runtime_command, json.dumps(fetch_payload)
    )

    containers = [
        client.V1Container(
            name="celery-worker",
            image=image_name,
            command=["/bin/sh"],
            args=["/scripts/entrypoint.sh"],
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
            volume_mounts=[
                client.V1VolumeMount(name="script-volume", mount_path="/scripts"),
                client.V1VolumeMount(mount_path="/userfunc", name="userfunc"),
                client.V1VolumeMount(mount_path="/secrets", name="secrets"),
            ],
        ),
        client.V1Container(
            name="fetcher",
            image="fission/fetcher:v1.20.0",
            image_pull_policy="IfNotPresent",
            command=[
                "/fetcher",
                "-secret-dir",
                "/secrets",
                "-cfgmap-dir",
                "/configs",
                "/userfunc",
            ],
            env=[
                client.V1EnvVar(name="OTEL_EXPORTER_OTLP_INSECURE", value="true"),
                client.V1EnvVar(
                    name="OTEL_PROPAGATORS",
                    value="tracecontext,baggage",
                ),
                client.V1EnvVar(name="OTEL_EXPORTER_OTLP_ENDPOINT"),
                client.V1EnvVar(name="OTEL_TRACES_SAMPLER_ARG", value="0.1"),
                client.V1EnvVar(
                    name="OTEL_TRACES_SAMPLER",
                    value="parentbased_traceidratio",
                ),
            ],
            liveness_probe=client.V1Probe(
                failure_threshold=3,
                http_get=client.V1HTTPGetAction(
                    path="/healthz", port=8000, scheme="HTTP"
                ),
                initial_delay_seconds=1,
                period_seconds=5,
                success_threshold=1,
                timeout_seconds=1,
            ),
            readiness_probe=client.V1Probe(
                failure_threshold=30,
                http_get=client.V1HTTPGetAction(
                    path="/readiness-healthz", port=8000, scheme="HTTP"
                ),
                initial_delay_seconds=1,
                period_seconds=1,
                success_threshold=1,
                timeout_seconds=1,
            ),
            resources=client.V1ResourceRequirements(
                requests={"cpu": "10m", "memory": "16Mi"}
            ),
            termination_message_path="/dev/termination-log",
            termination_message_policy="File",
            volume_mounts=[
                client.V1VolumeMount(mount_path="/userfunc", name="userfunc"),
                client.V1VolumeMount(mount_path="/secrets", name="secrets"),
                client.V1VolumeMount(mount_path="/configs", name="configmaps"),
                client.V1VolumeMount(mount_path="/etc/podinfo", name="podinfo"),
            ],
        ),
    ]

    volumes = [
        client.V1Volume(
            name="script-volume",
            config_map=client.V1ConfigMapVolumeSource(
                name="entrypoint-script", default_mode=0o755
            ),
        ),
        client.V1Volume(name="userfunc", empty_dir=client.V1EmptyDirVolumeSource()),
        client.V1Volume(name="secrets", empty_dir=client.V1EmptyDirVolumeSource()),
        client.V1Volume(name="configmaps", empty_dir=client.V1EmptyDirVolumeSource()),
        client.V1Volume(
            name="podinfo",
            downward_api=client.V1DownwardAPIVolumeSource(
                items=[
                    client.V1DownwardAPIVolumeFile(
                        path="name",
                        field_ref=client.V1ObjectFieldSelector(
                            field_path="metadata.name"
                        ),
                    ),
                    client.V1DownwardAPIVolumeFile(
                        path="namespace",
                        field_ref=client.V1ObjectFieldSelector(
                            field_path="metadata.namespace"
                        ),
                    ),
                ]
            ),
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
                    volumes=volumes,
                ),
            ),
        ),
    )
    apply_resource(deployment)


def create_celery_workers(
    config: CloudConfig,
    runtime_command: str,
    task_name: str,
    drain_existing_task: bool = True,
) -> None:
    namespace = JOBS_NS
    service_account_name = CELERY_WORKER_SA
    package_ns = FISSION_CRD_NS

    # Create the namespace and service account for celery workers
    create_namespace(namespace)
    create_service_account(namespace, service_account_name)

    # Create a namespaced role for accessing fission packages
    create_role(
        package_ns,
        "package-reader",
        [
            client.V1PolicyRule(
                api_groups=["fission.io"],
                resources=["packages"],
                verbs=["get", "list", "watch"],
            )
        ],
    )

    # Create a role binding in the namespace of the package resource. The role
    # binding will allow the celery workers to read the package resource.
    create_role_binding(
        package_ns,
        "package-reader-binding",
        "package-reader",
        namespace,
        service_account_name,
    )

    deployment_name = "celery-worker"

    create_deployment(
        runtime_command,
        task_name,
        namespace,
        deployment_name,
        service_account_name,
        "python:slim",
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

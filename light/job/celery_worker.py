from kubernetes import client
from light.k8s import create_namespace, apply_resource
from light.config import CloudConfig
from light.job.entrypoint import write_entrypoint_script_to_cfgmap
from light.job.utils import get_package_details
import json


def create_celery_workers(
    config: CloudConfig,
    runtime_command: str,
    task_name: str,
    drain_existing_task: bool = True,
) -> None:
    project = config.cluster.name

    api = client.CoreV1Api()

    # Create a namespace
    create_namespace(project, "celery-workers")

    # Create a service account
    service_account = client.V1ServiceAccount(
        kind="ServiceAccount",
        metadata=client.V1ObjectMeta(
            name="celery-worker-sa", namespace="celery-workers"
        ),
    )
    apply_resource(project, service_account)

    # Create a Kubernetes RoleBinding that authorizes the service account to read the Redis secret
    role_binding = client.V1RoleBinding(
        kind="RoleBinding",
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

    # Define the Role
    role = client.V1Role(
        api_version="rbac.authorization.k8s.io/v1",
        kind="Role",
        metadata=client.V1ObjectMeta(name="package-reader", namespace="default"),
        rules=[
            client.V1PolicyRule(
                api_groups=["fission.io"],
                resources=["packages"],
                verbs=["get", "list", "watch"],
            )
        ],
    )
    apply_resource(project, role)

    # Define the RoleBinding
    role_binding = client.V1RoleBinding(
        api_version="rbac.authorization.k8s.io/v1",
        kind="RoleBinding",
        metadata=client.V1ObjectMeta(
            name="package-reader-binding", namespace="default"
        ),
        subjects=[
            client.V1Subject(
                kind="ServiceAccount",
                name="celery-worker-sa",
                namespace="celery-workers",
            )
        ],
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io", kind="Role", name="package-reader"
        ),
    )
    apply_resource(project, role_binding)

    config_map = client.V1ConfigMap(
        kind="ConfigMap",
        metadata=client.V1ObjectMeta(
            name="celery-workers-config", namespace="celery-workers"
        ),
        data={
            "redis-host": "redis-master.redis.svc.cluster.local",
        },
    )
    apply_resource(project, config_map)

    package = get_package_details(config, "default", task_name)
    # 0 = FETCH_SOURCE 1 = FETCH_DEPLOYMENT 2 = FETCH_URL
    fetch_payload = {
        "FetchType": 1,
        "FileName": task_name,
        "Package": {
            "Name": task_name,
            "Namespace": "default",
            "ResourceVersion": package.metadata.resourceVersion,
        },
        "KeepArchive": False,
    }

    write_entrypoint_script_to_cfgmap(
        config, runtime_command, json.dumps(fetch_payload)
    )

    # Create a deployment
    deployment = client.V1Deployment(
        kind="Deployment",
        metadata=client.V1ObjectMeta(name="celery-worker", namespace="celery-workers"),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"name": "celery-worker"}),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"name": "celery-worker"}),
                spec=client.V1PodSpec(
                    service_account_name="celery-worker-sa",
                    containers=[
                        client.V1Container(
                            name="celery-worker",
                            image="python:slim",
                            command=["/bin/sh"],
                            args=["/scripts/entrypoint.sh"],
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
                            ],
                            volume_mounts=[
                                client.V1VolumeMount(
                                    name="script-volume", mount_path="/scripts"
                                ),
                                client.V1VolumeMount(
                                    mount_path="/userfunc", name="userfunc"
                                ),
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
                                client.V1EnvVar(
                                    name="OTEL_EXPORTER_OTLP_INSECURE", value="true"
                                ),
                                client.V1EnvVar(
                                    name="OTEL_PROPAGATORS",
                                    value="tracecontext,baggage",
                                ),
                                client.V1EnvVar(name="OTEL_EXPORTER_OTLP_ENDPOINT"),
                                client.V1EnvVar(
                                    name="OTEL_TRACES_SAMPLER_ARG", value="0.1"
                                ),
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
                                client.V1VolumeMount(
                                    mount_path="/userfunc", name="userfunc"
                                ),
                                client.V1VolumeMount(
                                    mount_path="/secrets", name="secrets"
                                ),
                                client.V1VolumeMount(
                                    mount_path="/configs", name="configmaps"
                                ),
                                client.V1VolumeMount(
                                    mount_path="/etc/podinfo", name="podinfo"
                                ),
                            ],
                        ),
                    ],
                    volumes=[
                        client.V1Volume(
                            name="script-volume",
                            config_map=client.V1ConfigMapVolumeSource(
                                name="entrypoint-script", default_mode=0o755
                            ),
                        ),
                        client.V1Volume(
                            name="userfunc", empty_dir=client.V1EmptyDirVolumeSource()
                        ),
                        client.V1Volume(
                            name="secrets", empty_dir=client.V1EmptyDirVolumeSource()
                        ),
                        client.V1Volume(
                            name="configmaps", empty_dir=client.V1EmptyDirVolumeSource()
                        ),
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
                    ],
                ),
            ),
        ),
    )
    apply_resource(project, deployment)

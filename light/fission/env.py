import re
from typing import Optional

from kubernetes import client

from light.k8s import (
    CustomResource,
    apply_resource,
    delete_namespaced_custom_object,
    list_namespaced_custom_object,
    read_namespaced_custom_object,
)


def validate_resource_format(resource: str, resource_type: str) -> None:
    cpu_pattern = r"^\d+(\.\d+)?(m)?$"
    memory_pattern = r"^\d+(E|Ei|P|Pi|T|Ti|G|Gi|M|Mi|K|Ki)?$"

    if resource_type == "cpu" and not re.match(cpu_pattern, resource):
        raise ValueError(
            "Invalid CPU format. It should be a number representing cores (e.g., 0.5 for half a core) or a number followed by 'm' representing milliCPU units (e.g., 500m for half a core)."
        )
    elif resource_type == "memory" and not re.match(memory_pattern, resource):
        raise ValueError(
            "Invalid memory format. It should be a number followed by a unit of bytes (e.g., 500Mi for 500 Mebibytes)."
        )


def upsert_env(
    env_name: str,
    env_namespace: str,
    image: str,
    builder_image: str,
    builder_command: str = "build",
    pool_size: int = 1,
    keep_archive: bool = False,
    image_pull_secret: str = "",
    min_cpu: Optional[str] = None,
    max_cpu: Optional[str] = None,
    min_memory: Optional[str] = None,
    max_memory: Optional[str] = None,
) -> dict:
    resources = {}
    if min_cpu:
        validate_resource_format(min_cpu, "cpu")
        resources["requests"] = {"cpu": min_cpu}
    if max_cpu:
        validate_resource_format(max_cpu, "cpu")
        resources["limits"] = {"cpu": max_cpu}
    if min_memory:
        validate_resource_format(min_memory, "memory")
        resources["requests"] = {"memory": min_memory}
    if max_memory:
        validate_resource_format(max_memory, "memory")
        resources["limits"] = {"memory": max_memory}

    env_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Environment",
        plural="environments",
        metadata=client.V1ObjectMeta(name=env_name, namespace=env_namespace),
        spec={
            # version 3 supports pre-warmed pool size adjustment
            "version": 3,
            "runtime": {
                "image": image,
                "container": {"name": "", "resources": {}},
            },
            "resources": resources,
            "poolsize": pool_size,
            "keeparchive": keep_archive,
            "imagepullsecret": image_pull_secret,
            "builder": {
                "image": builder_image,
                "command": builder_command,
                "container": {"name": "", "resources": {}},
            },
        },
    )
    apply_resource(env_crd)

    return env_crd.metadata.to_dict()


def get_env(
    env_name: str,
    env_namespace: str,
) -> dict:
    env_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Environment",
        plural="environments",
        metadata=client.V1ObjectMeta(name=env_name, namespace=env_namespace),
        spec={},
    )

    env = read_namespaced_custom_object(env_name, env_namespace, env_crd)

    return env


def delete_env(
    env_name: str,
    env_namespace: str,
) -> None:
    env_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Environment",
        plural="environments",
        metadata=client.V1ObjectMeta(name=env_name, namespace=env_namespace),
        spec={},
    )

    delete_namespaced_custom_object(env_name, env_namespace, env_crd)


def list_envs(
    env_namespace: str,
) -> dict:
    env_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Environment",
        plural="environments",
        metadata=client.V1ObjectMeta(namespace=env_namespace),
        spec={},
    )

    envs = list_namespaced_custom_object(env_namespace, env_crd)

    return envs

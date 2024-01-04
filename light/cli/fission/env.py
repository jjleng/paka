from kubernetes import client
from light.k8s import (
    CustomResource,
    apply_resource,
    load_kubeconfig,
    read_namespaced_custom_object,
    delete_namespaced_custom_object,
    list_namespaced_custom_object,
)


def upsert_env(
    kubeconfig_name: str,
    env_name: str,
    env_namespace: str,
    image: str,
    builder_image: str,
    builder_command: str = "build",
    pool_size: int = 1,
    keep_archive: bool = False,
    image_pull_secret: str = "",
) -> dict:
    env_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Environment",
        plural="environments",
        metadata=client.V1ObjectMeta(name=env_name, namespace=env_namespace),
        spec={
            "version": 2,
            "runtime": {
                "image": image,
                "container": {"name": "", "resources": {}},  # TODO: add resources
            },
            "resources": {},
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
    apply_resource(kubeconfig_name, env_crd)

    return env_crd.metadata.to_dict()


def get_env(
    kubeconfig_name: str,
    env_name: str,
    env_namespace: str,
) -> dict:
    load_kubeconfig(kubeconfig_name)
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
    kubeconfig_name: str,
    env_name: str,
    env_namespace: str,
) -> None:
    load_kubeconfig(kubeconfig_name)
    env_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Environment",
        plural="environments",
        metadata=client.V1ObjectMeta(name=env_name, namespace=env_namespace),
        spec={},
    )

    delete_namespaced_custom_object(env_name, env_namespace, env_crd)


def list_envs(
    kubeconfig_name: str,
    env_namespace: str,
) -> dict:
    load_kubeconfig(kubeconfig_name)
    env_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Environment",
        plural="environments",
        metadata=client.V1ObjectMeta(namespace=env_namespace),
        spec={},
    )

    envs = list_namespaced_custom_object(env_namespace, env_crd)

    return envs

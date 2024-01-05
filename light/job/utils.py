import json
from typing import Any

from kubernetes import client

from light.job.entrypoint import write_entrypoint_script_to_cfgmap
from light.k8s import CustomResource, create_namespace, read_namespaced_custom_object


def get_package_details(namespace: str, package_name: str) -> Any:
    package_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Package",
        plural="packages",
        metadata=client.V1ObjectMeta(name=package_name, namespace=namespace),
        spec={},
    )

    package = read_namespaced_custom_object(package_name, namespace, package_crd)

    # Print details of the Package
    print("Package Details:\n")
    print(f"Name: {package.metadata.name}")
    print(f"Namespace: {package.metadata.namespace}")
    print(f"Resource Version: {package.metadata.resourceVersion}")
    print(f"Spec: {package.spec}")
    print(f"Status: {package.status}")
    return package


def test_write_entrypoint(namespace: str, package_name: str) -> None:
    package = get_package_details(namespace, package_name)

    fetch_payload = {
        "FetchType": 1,
        "FileName": package_name,
        "Package": {
            "Name": package_name,
            "Namespace": namespace,
            "ResourceVersion": package.metadata.resourceVersion,
        },
        "KeepArchive": False,
    }

    create_namespace("celery-workers")
    write_entrypoint_script_to_cfgmap(
        "jobs", "celery -A celery.main worker", json.dumps(fetch_payload)
    )

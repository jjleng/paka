from kubernetes import client
from kubernetes.dynamic import DynamicClient
from typing import Any
from light.job.entrypoint import write_entrypoint_script_to_cfgmap
import json
from light.k8s import create_namespace


def get_package_details(namespace: str, package_name: str) -> Any:
    # Create a dynamic client
    k8s_client = client.api_client.ApiClient()
    dynamic_client = DynamicClient(k8s_client)

    # Define the API version and kind for the Package resource
    package_group = "fission.io"
    package_version = "v1"
    package_plural = "packages"  # Plural form of the CRD as defined in its definition

    # Fetch the Package resource
    package_api = dynamic_client.resources.get(
        api_version=f"{package_group}/{package_version}", kind="Package"
    )
    package = package_api.get(namespace=namespace, name=package_name)

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

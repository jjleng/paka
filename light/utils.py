import os
from pathlib import Path
import json
from ruamel.yaml import YAML
from kubernetes import config
from io import StringIO
from light.constants import PROJECT_NAME
import re
from typing import Any
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from typing import Protocol, Literal


class KubernetesResource(Protocol):
    metadata: client.V1ObjectMeta
    kind: Literal["Deployment", "Service", "HorizontalPodAutoscaler"]


def camel_to_kebab(name: str) -> str:
    name = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", name).lower()


def sanitize_k8s_name(name: str) -> str:
    """
    Sanitize a string to be compliant with Kubernetes resource naming conventions.

    Args:
    name (str): The original name string.

    Returns:
    str: The sanitized name string.
    """

    # Convert to lowercase
    sanitized_name = name.lower()

    # Replace any disallowed characters with '-'
    sanitized_name = re.sub(r"[^a-z0-9\-]", "-", sanitized_name)

    # Remove leading or trailing non-alphanumeric characters
    sanitized_name = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", sanitized_name)

    return sanitized_name


def get_project_data_dir() -> str:
    """
    Get the project data directory.

    Returns:
        str: The project data directory.
    """
    home = Path.home()
    return os.path.join(home, f".{camel_to_kebab(PROJECT_NAME)}")


def save_kubeconfig(name: str, kubeconfig_json: str) -> None:
    """
    Save the kubeconfig data as YAML file.

    Args:
        name (str): The name of the kubeconfig file.
        kubeconfig_json (str): The kubeconfig data in JSON format.

    Returns:
        None
    """
    kubeconfig_data = json.loads(kubeconfig_json)

    yaml = YAML()

    buf = StringIO()
    yaml.dump(kubeconfig_data, buf)
    kubeconfig_yaml = buf.getvalue()

    kubeconfig_file_path = os.path.join(get_project_data_dir(), name)
    os.makedirs(os.path.dirname(kubeconfig_file_path), exist_ok=True)

    with open(kubeconfig_file_path, "w") as f:
        f.write(kubeconfig_yaml)


def load_kubeconfig(name: str) -> None:
    """
    Load the kubeconfig data from a YAML file.

    Args:
        name (str): The name of the kubeconfig file.

    Returns:
        None
    """
    kubeconfig_file_path = os.path.join(get_project_data_dir(), name)

    config.load_kube_config(kubeconfig_file_path)


def apply_resource(
    kubeconfig_name: str,
    resource: KubernetesResource,
) -> Any:
    # Load the Kubernetes configuration
    load_kubeconfig(kubeconfig_name)

    # Determine the resource kind and prepare the appropriate API client
    kind = resource.kind
    namespace = resource.metadata.namespace or "default"

    if kind == "Deployment":
        api = client.AppsV1Api()
        create_method = api.create_namespaced_deployment
        replace_method = api.replace_namespaced_deployment
        read_method = api.read_namespaced_deployment
    elif kind == "Service":
        api = client.CoreV1Api()
        create_method = api.create_namespaced_service
        replace_method = api.replace_namespaced_service
        read_method = api.read_namespaced_service
    elif kind == "HorizontalPodAutoscaler":
        api = client.AutoscalingV2Api()
        create_method = api.create_namespaced_horizontal_pod_autoscaler
        replace_method = api.replace_namespaced_horizontal_pod_autoscaler
        read_method = api.read_namespaced_horizontal_pod_autoscaler
    else:
        raise ValueError(f"Unsupported kind: {kind}")

    # Try to read (get) the resource; if it exists, replace it, otherwise create it
    try:
        read_method(resource.metadata.name, namespace)
        response = replace_method(resource.metadata.name, namespace, resource)
        print(f"{kind} '{resource.metadata.name}' updated.")
    except ApiException as e:
        if e.status == 404:
            response = create_method(namespace, resource)
            print(f"{kind} '{resource.metadata.name}' created.")
        else:
            raise e

    return response

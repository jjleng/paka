from kubernetes import client
from typing import Any, Dict
import re
import os
from kubernetes.client.rest import ApiException
from typing import Protocol, Literal
import json
from ruamel.yaml import YAML
from kubernetes import config
from io import StringIO
from light.utils import get_project_data_dir
from functools import partial


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


class CustomResource:
    def __init__(
        self,
        api_version: str,
        kind: str,
        plural: str,
        spec: Dict[str, Any],
        metadata: Dict[str, Any],
    ):
        # Ensure api_version is in the format group/version
        if not re.match(r"^.+/v\d+$", api_version):
            raise ValueError("api_version must be in the format 'group/version'")
        self.api_version = api_version
        self.group, self.version = api_version.split("/")
        self.kind = kind
        self.plural = plural
        self.metadata = metadata
        self.spec = spec


def create_namespaced_custom_object(namespace: str, resource: CustomResource) -> Any:
    body = {
        "apiVersion": resource.api_version,
        "kind": resource.kind,
        "metadata": {
            "name": resource.metadata["name"],
            "namespace": namespace,
            **resource.metadata,
        },
        "spec": resource.spec,
    }
    api_instance = client.CustomObjectsApi()

    return api_instance.create_namespaced_custom_object(
        group=resource.group,
        version=resource.version,
        namespace=namespace,
        plural=resource.plural,
        body=body,
    )


def read_namespaced_custom_object(
    name: str, namespace: str, resource: CustomResource
) -> Any:
    api_instance = client.CustomObjectsApi()
    return api_instance.get_namespaced_custom_object(
        group=resource.group,
        version=resource.version,
        namespace=namespace,
        plural=resource.plural,
        name=name,
    )


def replace_namespaced_custom_object(
    name: str, namespace: str, resource: CustomResource
) -> Any:
    body = {
        "apiVersion": resource.api_version,
        "kind": resource.kind,
        "metadata": {
            "name": resource.metadata["name"],
            "namespace": namespace,
            **resource.metadata,
        },
        "spec": resource.spec,
    }
    api_instance = client.CustomObjectsApi()
    return api_instance.replace_namespaced_custom_object(
        group=resource.group,
        version=resource.version,
        namespace=namespace,
        plural=resource.plural,
        name=name,
        body=body,
    )


class KubernetesResource(Protocol):
    metadata: client.V1ObjectMeta
    kind: Literal[
        "Deployment",
        "Service",
        "HorizontalPodAutoscaler",
        "ScaledObject",
        "ServiceAccount",
        "Secret",
        "RoleBinding",
        "ConfigMap",
        "Role",
    ]


def apply_resource(
    kubeconfig_name: str,
    resource: KubernetesResource,
) -> Any:
    """
    Applies a Kubernetes resource by creating or updating it.

    Args:
        kubeconfig_name (str): The name of the kubeconfig file to use.
        resource (KubernetesResource): The Kubernetes resource to apply.

    Returns:
        Any: The response from the API call.

    Raises:
        ValueError: If the resource kind is unsupported.
        ApiException: If an error occurs while creating or updating the resource.
    """
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
    elif kind == "ScaledObject":
        create_method = create_namespaced_custom_object
        replace_method = replace_namespaced_custom_object
        read_method = partial(read_namespaced_custom_object, resource=resource)
    elif kind == "ServiceAccount":
        api = client.CoreV1Api()
        create_method = api.create_namespaced_service_account
        replace_method = api.patch_namespaced_service_account
        read_method = api.read_namespaced_service_account
    elif kind == "Secret":
        api = client.CoreV1Api()
        create_method = api.create_namespaced_secret
        replace_method = api.patch_namespaced_secret
        read_method = api.read_namespaced_secret
    elif kind == "RoleBinding":
        api = client.RbacAuthorizationV1Api()
        create_method = api.create_namespaced_role_binding
        replace_method = api.patch_namespaced_role_binding
        read_method = api.read_namespaced_role_binding
    elif kind == "Role":
        api = client.RbacAuthorizationV1Api()
        create_method = api.create_namespaced_role
        replace_method = api.patch_namespaced_role
        read_method = api.read_namespaced_role
    elif kind == "ConfigMap":
        api = client.CoreV1Api()
        create_method = api.create_namespaced_config_map
        replace_method = api.patch_namespaced_config_map
        read_method = api.read_namespaced_config_map
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


def create_namespace(kubeconfig_name: str, name: str) -> None:
    """
    Creates a Kubernetes namespace.

    Args:
        name (str): The name of the namespace to create.

    Returns:
        None

    Raises:
        ApiException: If an error occurs while creating the namespace.
    """
    # Load the Kubernetes configuration
    load_kubeconfig(kubeconfig_name)

    api = client.CoreV1Api()
    namespace = client.V1Namespace(metadata=client.V1ObjectMeta(name=name))
    try:
        api.create_namespace(body=namespace)
    except ApiException as e:
        if e.status == 409:  # Conflict, namespace already exists
            pass
        else:
            raise


def create_service_account(
    kubeconfig_name: str, namespace: str, account_name: str
) -> None:
    service_account = client.V1ServiceAccount(
        kind="ServiceAccount",
        metadata=client.V1ObjectMeta(name=account_name, namespace=namespace),
    )
    apply_resource(kubeconfig_name, service_account)


def create_role_binding(
    kubeconfig_name: str,
    binding_namespace: str,
    binding_name: str,
    role_name: str,
    subject_namespace: str,
    service_account_name: str,
) -> None:
    role_binding = client.V1RoleBinding(
        kind="RoleBinding",
        metadata=client.V1ObjectMeta(name=binding_name, namespace=binding_namespace),
        subjects=[
            client.V1Subject(
                kind="ServiceAccount",
                name=service_account_name,
                namespace=subject_namespace,
            )
        ],
        role_ref=client.V1RoleRef(
            api_group="rbac.authorization.k8s.io", kind="Role", name=role_name
        ),
    )
    apply_resource(kubeconfig_name, role_binding)


def create_config_map(
    kubeconfig_name: str, namespace: str, map_name: str, data: dict
) -> None:
    config_map = client.V1ConfigMap(
        kind="ConfigMap",
        metadata=client.V1ObjectMeta(name=map_name, namespace=namespace),
        data=data,
    )
    apply_resource(kubeconfig_name, config_map)


def create_role(
    kubeconfig_name: str, namespace: str, role_name: str, rules: list
) -> None:
    role = client.V1Role(
        api_version="rbac.authorization.k8s.io/v1",
        kind="Role",
        metadata=client.V1ObjectMeta(name=role_name, namespace=namespace),
        rules=rules,
    )
    apply_resource(kubeconfig_name, role)

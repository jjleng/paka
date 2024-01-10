import json
import os
import re
from io import StringIO
from pathlib import Path
from typing import Any, Callable

from ruamel.yaml import YAML

from light.constants import PROJECT_NAME


def camel_to_kebab(name: str) -> str:
    """
    Converts a camel case string to kebab case.

    Args:
        name (str): The camel case string to be converted.

    Returns:
        str: The kebab case string.

    Example:
        >>> camel_to_kebab("camelCaseString")
        'camel-case-string'
    """
    name = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", name).lower()


def kubify_name(old: str) -> str:
    max_len = 63

    new_name = old.lower()

    # replace disallowed chars with '-'
    new_name = re.sub(r"[^-a-z0-9]", "-", new_name)

    # trim leading non-alphabetic
    new_name = re.sub(r"^[^a-z]+", "", new_name)

    # trim trailing
    new_name = re.sub(r"[^a-z0-9]+$", "", new_name)

    # truncate to length
    if len(new_name) > max_len:
        new_name = new_name[:max_len]

    if len(new_name) == 0:
        raise Exception(f"Name: {old} can't be converted to a valid Kubernetes name")

    return new_name


def get_project_data_dir() -> str:
    """
    Get the project data directory.

    Returns:
        str: The project data directory.
    """
    home = Path.home()
    return os.path.join(home, f".{camel_to_kebab(PROJECT_NAME)}")


def call_once(func: Callable) -> Callable:
    """Decorator to ensure a function is only called once."""
    has_been_called = False

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        nonlocal has_been_called
        if not has_been_called:
            has_been_called = True
            return func(*args, **kwargs)

    return wrapper


def to_yaml(obj: dict) -> str:
    """
    Converts an object to a YAML string.

    Args:
        obj (dict): The object to be converted.

    Returns:
        str: The YAML string.
    """
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    buf = StringIO()
    yaml.dump(obj, buf)
    return buf.getvalue()


def set_current_cluster(name: str) -> None:
    # Create symlink that points to the current cluster
    target = get_cluster_data_dir(name)

    # Path where the symlink should be created
    link = os.path.join(get_project_data_dir(), "current_cluster")

    # Remove the existing symlink if it exists
    if os.path.islink(link):
        os.unlink(link)

    # Create a new symlink
    os.symlink(target, link)


def get_cluster_data_dir(name: str) -> str:
    """
    Get the cluster data directory.

    Args:
        name (str): The name of the cluster.

    Returns:
        str: The cluster data directory.
    """
    return os.path.join(get_project_data_dir(), "clusters", name)


def get_pulumi_data_dir() -> str:
    """
    Get the pulumi data directory.

    Returns:
        str: The pulumi data directory.
    """
    return os.path.join(get_project_data_dir(), "pulumi")


def save_kubeconfig(name: str, kubeconfig_json: str) -> None:
    """
    Save the kubeconfig data as YAML file.

    Args:
        name (str): The name of the cluster.
        kubeconfig_json (str): The kubeconfig data in JSON format.

    Returns:
        None
    """
    kubeconfig_data = json.loads(kubeconfig_json)

    kubeconfig_file_path = os.path.join(get_cluster_data_dir(name), "kubeconfig.yaml")
    os.makedirs(os.path.dirname(kubeconfig_file_path), exist_ok=True)

    with open(kubeconfig_file_path, "w") as f:
        f.write(to_yaml(kubeconfig_data))

    set_current_cluster(name)


def save_cluster_data(name: str, k: str, v: Any) -> None:
    """
    Save the cluster data as YAML file.

    Args:
        name (str): The name of the cluster.
        k (str): The key of the cluster data.
        v (Any): The value of the cluster data.
    Returns:
        None
    """

    yaml = YAML()
    cluster_file_path = os.path.join(get_cluster_data_dir(name), "cluster.yaml")
    os.makedirs(os.path.dirname(cluster_file_path), exist_ok=True)

    # Load the existing data
    try:
        with open(cluster_file_path, "r") as file:
            data = yaml.load(file)
    except FileNotFoundError:
        data = {}

    data[k] = v

    with open(cluster_file_path, "w") as file:
        yaml.dump(data, file)


def read_cluster_data_by_path(path: str, k: str) -> Any:
    yaml = YAML()
    # Load the existing data
    try:
        with open(path, "r") as file:
            data = yaml.load(file)
    except FileNotFoundError:
        return None

    return data.get(k)


def read_cluster_data(name: str, k: str) -> Any:
    """
    Read the cluster data.

    Args:
        name (str): The name of the cluster.
        k (str): The key of the cluster data.

    Returns:
        Any: The value of the cluster data.
    """
    cluster_file_path = os.path.join(get_cluster_data_dir(name), "cluster.yaml")
    return read_cluster_data_by_path(cluster_file_path, k)


def read_current_cluster_data(k: str) -> Any:
    """
    Read the cluster data.

    Args:
        name (str): The name of the cluster.
        k (str): The key of the cluster data.

    Returns:
        Any: The value of the cluster data.
    """
    cluster_file_path = os.path.join(
        get_project_data_dir(), "current_cluster", "cluster.yaml"
    )
    return read_cluster_data_by_path(cluster_file_path, k)

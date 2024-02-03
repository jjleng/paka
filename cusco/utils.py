import json
import os
import random
import re
import string
from functools import lru_cache
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ruamel.yaml import YAML

from cusco.constants import HOME_ENV_VAR, PROJECT_NAME


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
    """
    Convert a string into a valid Kubernetes name.

    This function takes a string, converts it to lowercase, replaces disallowed characters with '-',
    trims leading non-alphabetic characters, trims trailing non-alphanumeric characters, and truncates
    it to a maximum length of 63 characters to create a valid Kubernetes name.

    If the resulting name is empty, it raises an exception.

    Args:
        old (str): The original string to be converted.

    Returns:
        str: The converted string that is a valid Kubernetes name.

    Raises:
        Exception: If the resulting name is empty.
    """
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

    This function retrieves the directory path where the project data is stored.
    If the environment variable HOME_ENV_VAR is set, it returns its value.
    Otherwise, it returns the home directory appended with the kebab-case project name.

    Returns:
        str: The absolute path of the project data directory.
    """
    return os.environ.get(
        HOME_ENV_VAR, os.path.join(Path.home(), f".{camel_to_kebab(PROJECT_NAME)}")
    )


def call_once(func: Callable) -> Callable:
    """
    Decorator to ensure a function is only executed once.
    """
    has_been_called = False

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        nonlocal has_been_called
        if not has_been_called:
            has_been_called = True
            return func(*args, **kwargs)

    return wrapper


def to_yaml(obj: Dict[str, Any]) -> str:
    """
    Converts an dictionary to a YAML string.

    Args:
        obj (dict): The dictionary to be converted.

    Returns:
        str: The YAML string.
    """
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    buf = StringIO()
    yaml.dump(obj, buf)
    return buf.getvalue()


def read_yaml_file(path: str) -> Dict[str, Any]:
    """
    Reads a YAML file and returns its contents as a dictionary.

    This function opens a YAML file, reads its contents, and converts it into a Python dictionary.
    If the file does not exist, it returns an empty dictionary.

    Args:
        path (str): The path to the YAML file.

    Returns:
        Dict[str, Any]: The contents of the YAML file as a dictionary, or an empty dictionary if the file does not exist.
    """
    yaml = YAML()
    try:
        with open(path, "r") as file:
            data = yaml.load(file)
    except FileNotFoundError:
        data = {}
    return data or {}


def set_current_cluster(cluster_name: str) -> None:
    """
    Sets the specified cluster as the current cluster.

    This function creates a symbolic link that points to the data directory of the specified cluster.
    The symbolic link is created in the project data directory and is named "current_cluster".
    If a symbolic link with this name already exists, it is removed before the new link is created.

    Args:
        cluster_name (str): The name of the cluster to be set as the current cluster.
    """
    target = get_cluster_data_dir(cluster_name)

    link = os.path.join(get_project_data_dir(), "current_cluster")

    if os.path.islink(link):
        os.unlink(link)

    os.symlink(target, link)


def get_cluster_data_dir(cluster_name: str) -> str:
    """
    Get the cluster data directory.

    Args:
        name (str): The name of the cluster.

    Returns:
        str: The cluster data directory.
    """
    return os.path.join(get_project_data_dir(), "clusters", cluster_name)


def get_pulumi_root() -> str:
    """
    Get the pulumi data directory.

    Returns:
        str: The pulumi data directory.
    """
    return get_project_data_dir()


def save_kubeconfig(cluster_name: str, kubeconfig_json: Optional[str]) -> None:
    """
    Save the kubeconfig data as a YAML file named 'kubeconfig.yaml'.

    This function takes the kubeconfig data in JSON format, converts it to YAML,
    and saves it to a file named 'kubeconfig.yaml'. The file is stored
    in the directory specified by the cluster name.

    Args:
        cluster_name (str): The name of the cluster. This is used to determine the directory where the kubeconfig file will be saved.
        kubeconfig_json (str): The kubeconfig data in JSON format.

    Returns:
        None
    """
    if kubeconfig_json is None:
        return

    kubeconfig_data = json.loads(kubeconfig_json)

    kubeconfig_file_path = os.path.join(
        get_cluster_data_dir(cluster_name), "kubeconfig.yaml"
    )
    os.makedirs(os.path.dirname(kubeconfig_file_path), exist_ok=True)

    with open(kubeconfig_file_path, "w") as f:
        f.write(to_yaml(kubeconfig_data))

    set_current_cluster(cluster_name)


def save_cluster_data(cluster_name: str, k: str, v: Any) -> None:
    """
    Save or update the cluster data in a YAML file named 'cluster.yaml'.

    This function takes a key-value pair of cluster data and upserts it into the 'cluster.yaml' file.
    If the key already exists in the file, its value is updated. If the key does not exist, it is added to the file.
    The 'cluster.yaml' file is stored in the directory specified by the cluster name.

    Args:
        name (str): The name of the cluster. This is used to determine the directory where the 'cluster.yaml' file is located.
        k (str): The key of the cluster data.
        v (Any): The value of the cluster data.

    Returns:
        None
    """

    cluster_file_path = os.path.join(get_cluster_data_dir(cluster_name), "cluster.yaml")
    os.makedirs(os.path.dirname(cluster_file_path), exist_ok=True)

    data = read_yaml_file(cluster_file_path)
    data[k] = v

    yaml = YAML()
    with open(cluster_file_path, "w") as file:
        yaml.dump(data, file)


@lru_cache(maxsize=100)
def read_cluster_data_by_path(path: str, k: str) -> Any:
    """
    Reads cluster data from a YAML file at a given path.

    This function opens a YAML file at the specified path, reads its contents into a Python dictionary,
    and returns the value associated with the provided key. If the key does not exist in the dictionary,
    it returns None.

    Args:
        path (str): The path to the YAML file.
        k (str): The key of the data to be retrieved.

    Returns:
        Any: The value associated with the key in the YAML file, or None if the key does not exist.
    """
    data = read_yaml_file(path)
    return data.get(k)


def read_cluster_data(cluster_name: str, k: str) -> Any:
    """
    Read specific data associated with a cluster.

    This function retrieves the value associated with a given key from the cluster data.
    The cluster data is stored in a YAML file named 'cluster.yaml' in the directory specified by the cluster name.

    Args:
        cluster_name (str): The name of the cluster. This is used to determine the directory where the 'cluster.yaml' file is located.
        k (str): The key of the data to be retrieved from the cluster data.

    Returns:
        Any: The value associated with the key in the cluster data, or None if the key does not exist.
    """
    cluster_file_path = os.path.join(get_cluster_data_dir(cluster_name), "cluster.yaml")
    return read_cluster_data_by_path(cluster_file_path, k)


def read_current_cluster_data(k: str) -> Any:
    """
    Read specific data associated with the current cluster.

    This function retrieves the value associated with a given key from the current cluster's data.
    The cluster data is stored in a YAML file named 'cluster.yaml' in the 'current_cluster' directory within the project data directory.

    Args:
        k (str): The key of the data to be retrieved from the cluster data.

    Returns:
        Any: The value associated with the key in the cluster data, or None if the key does not exist.
    """
    cluster_file_path = os.path.join(
        get_project_data_dir(), "current_cluster", "cluster.yaml"
    )
    return read_cluster_data_by_path(cluster_file_path, k)


def random_str(length: int = 5) -> str:
    """
    Generate a random string of a specified length.

    This function generates a random string of a given length. The string consists of
    both ASCII letters (both lowercase and uppercase) and digits.

    Args:
        length (int, optional): The length of the random string to be generated. Defaults to 5.

    Returns:
        str: The generated random string.
    """
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))

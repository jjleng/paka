from __future__ import annotations

import hashlib
import json
import os
import random
import re
import string
import tempfile
from contextlib import contextmanager
from enum import Enum
from functools import lru_cache, wraps
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Optional, TypeVar, cast

import boto3
import requests
from ruamel.yaml import YAML

from paka.constants import HOME_ENV_VAR, PROJECT_NAME, PULUMI_STACK_NAME

T = TypeVar("T", bound=Callable[..., Any])


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
        HOME_ENV_VAR, str(Path.home() / f".{camel_to_kebab(PROJECT_NAME)}")
    )


def call_once(func: T) -> T:
    """
    Decorator to ensure a function is only executed once.
    """
    has_been_called = False

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        nonlocal has_been_called
        if not has_been_called:
            has_been_called = True
            return func(*args, **kwargs)

    return cast(T, wrapper)


def to_yaml(obj: Dict[Any, Any]) -> str:
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
    return str(Path(get_project_data_dir()) / "pulumi")


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


def calculate_sha256(file_path: str) -> str:
    """
    Calculate the SHA-256 hash of a file.

    Args:
        file_path (str): The path to the file for which the SHA-256 hash is to be calculated.

    Returns:
        str: The SHA-256 hash of the file, as a hexadecimal string.
    """
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def get_gh_release_latest_version(repo: str) -> str:
    """
    Get the latest release version of a GitHub repository.

    This function queries the GitHub API to get the latest release version of a repository.

    Args:
        repo (str): The GitHub repository in the format 'owner/repo'.

    Returns:
        str: The latest release version of the repository.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return data["tag_name"]


@contextmanager
def download_url(url: str) -> Generator[str, None, None]:
    """
    Download a file from a URL and return the path to the downloaded file.

    Args:
        url (str): The URL of the file to be downloaded.

    Returns:
        str: The path to the downloaded file.
    """
    fd, tmp_file = tempfile.mkstemp()
    try:
        with os.fdopen(fd, "wb") as tf:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    tf.write(chunk)

            tf.flush()
            os.fsync(tf.fileno())

        yield tmp_file
    finally:
        os.remove(tmp_file)


class PulumiStackKey(Enum):
    NAMESPACE = "namespace"
    REGION = "region"
    PROVIDER = "provider"
    REGISTRY = "registry"
    BUCKET = "bucket"
    KUBECONFIG = "kubeconfig"


def read_pulumi_stack(cluster_name: str, key: str) -> Any:
    try:
        k = PulumiStackKey[key.upper()]
    except KeyError:
        raise ValueError(
            f"Invalid key: {key}. Expected one of: {list(PulumiStackKey.__members__.values())}"
        )
    stack_json = _load_pulumi_stack(cluster_name)

    return _read_pulumi_stack_by_key(stack_json, k)


@lru_cache(maxsize=100)
def _load_pulumi_stack(cluster_name: str) -> dict:
    pulumi_backend_url = os.environ.get("PULUMI_BACKEND_URL", "")

    if not pulumi_backend_url:
        raise Exception("Pulumi backend URL is not set")

    if pulumi_backend_url.startswith("file://"):
        pulumi_root = Path(get_pulumi_root())  # Windows support?
        pulumi_stack_file = (
            pulumi_root
            / ".pulumi"
            / "stacks"
            / cluster_name
            / f"{PULUMI_STACK_NAME}.json"
        )
        stack_json = json.loads(pulumi_stack_file.read_text())
    elif pulumi_backend_url.startswith("s3://"):
        s3 = boto3.client("s3")
        response = s3.get_object(
            Bucket=pulumi_backend_url[5:],
            Key=f".pulumi/stacks/{cluster_name}/{PULUMI_STACK_NAME}.json",
        )
        stack_json = json.loads(response["Body"].read().decode("utf-8"))
    else:
        raise Exception("Unsupported Pulumi backend URL")

    return stack_json


def _read_pulumi_stack_by_key(stack_json: dict, k: PulumiStackKey) -> Any:
    resources = stack_json["checkpoint"]["latest"]["resources"]

    # For now, we assume that the cloud is AWS
    if k == PulumiStackKey.PROVIDER:
        for resource in resources:
            if resource["type"] == "pulumi:providers:aws":
                return "aws"
    elif k == PulumiStackKey.REGION:
        for resource in resources:
            if resource["type"] == "pulumi:providers:aws":
                return resource["outputs"]["region"]
    elif k == PulumiStackKey.REGISTRY:
        for resource in resources:
            # Since we creating only one ECR repository, there is no need to use the resource urn
            if resource["type"] == "aws:ecr/repository:Repository":
                return resource["outputs"]["repositoryUrl"]
    elif k == PulumiStackKey.BUCKET:
        for resource in resources:
            # Since we creating only one S3 bucket, there is no need to use the resource urn
            if resource["type"] == "aws:s3/bucket:Bucket":
                return resource["outputs"]["bucket"]
    elif k == PulumiStackKey.NAMESPACE:
        for resource in resources:
            if resource["type"] == "kubernetes:core/v1:Namespace" and resource[
                "urn"
            ].endswith("app-ns"):
                return resource["outputs"]["metadata"]["name"]
        # If no namespace is found, return the default namespace
        return "default"
    elif k == PulumiStackKey.KUBECONFIG:
        for resource in resources:
            # Since we creating only one secret, there is no need to use the resource urn
            if resource["type"] == "eks:index:Cluster":
                return resource["outputs"]["core"]["kubeconfig"]

    raise Exception(f"Unsupported PulumiStackKey: {k}")


@lru_cache(maxsize=100)
def get_instance_info(provider: str, region: str, instance_type: str) -> Dict[str, Any]:
    if provider == "aws":
        # Get the CPU, memory and GPU count for the instance type with boto3
        ec2 = boto3.client("ec2", region_name=region)

        response = ec2.describe_instance_types(InstanceTypes=[instance_type])  # type: ignore

        instance_types = response.get("InstanceTypes", [])
        if instance_types:
            instance_type_info = instance_types[0]
            gpu_info = instance_type_info.get("GpuInfo", {})
            gpu, vram = gpu_info.get("Gpus", [{}])[0], gpu_info.get(
                "TotalGpuMemoryInMiB"
            )
            return {
                "cpu": instance_type_info.get("VCpuInfo", {}).get("DefaultVCpus"),
                "memory": instance_type_info.get("MemoryInfo", {}).get("SizeInMiB"),
                "gpu_count": gpu.get("Count"),
                "vram": vram,
                "gpu_manufacturer": gpu.get("Manufacturer"),
                "gpu_name": gpu.get("Name"),
            }
    else:
        raise Exception(f"Unsupported provider: {provider}")
    raise Exception(f"Unsupported provider: {provider}")

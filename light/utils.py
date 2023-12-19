import os
from pathlib import Path
import json
from ruamel.yaml import YAML
from kubernetes import config
from light.constants import PROJECT_NAME


def save_kubeconfig(name: str, kubeconfig_json: str) -> None:
    """
    Save the kubeconfig data as YAML file.

    Args:
        name (str): The name of the kubeconfig file.
        kubeconfig_json (str): The kubeconfig data in JSON format.

    Returns:
        None
    """
    home = Path.home()

    kubeconfig_data = json.loads(kubeconfig_json)

    yaml = YAML()

    kubeconfig_yaml = yaml.dump(kubeconfig_data)

    kubeconfig_file_path = os.path.join(home, PROJECT_NAME, name)

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
    home = Path.home()
    kubeconfig_file_path = os.path.join(home, PROJECT_NAME, name)

    config.load_kube_config(kubeconfig_file_path)

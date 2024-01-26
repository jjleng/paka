from typing import List

import typer

from light.cli.utils import load_cluster_manager
from light.k8s import update_kubeconfig as merge_update_kubeconfig
from light.logger import logger

cluster_app = typer.Typer()


@cluster_app.command()
def up(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file. The cluster config file is a "
        "YAML file that contains the configuration of the cluster",
    ),
    update_kubeconfig: bool = typer.Option(
        False,
        "--update-kubeconfig",
        "-u",
        help="Updates the default kubeconfig file (~/.kube/config) to include"
        "the connection details of the newly created Kubernetes cluster"
        "This allows kubectl to communicate with the new cluster.",
    ),
) -> None:
    """
    Creates or updates a Kubernetes cluster based on the provided configuration.
    """
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.create()
    if update_kubeconfig:
        logger.info("Updating kubeconfig...")
        merge_update_kubeconfig()
        logger.info("Successfully updated kubeconfig.")


@cluster_app.command()
def down(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file. The cluster config file is a "
        "YAML file that contains the configuration of the cluster",
    ),
) -> None:
    """
    Tears down the Kubernetes cluster, removing all associated resources and data.
    """
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.destroy()


@cluster_app.command()
def refresh(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file. The cluster config file is a "
        "YAML file that contains the configuration of the cluster",
    ),
) -> None:
    """
    Updates local states to match the current state of the resources in the cloud.
    """
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.refresh()


@cluster_app.command()
def preview(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file. The cluster config file is a "
        "YAML file that contains the configuration of the cluster",
    ),
    policy_packs: List[str] = typer.Option(
        [],
        "--policy-pack",
        "-p",
        help="Path to the policy pack.",
    ),
) -> None:
    """
    Previews the changes that will be applied to the cloud resources.
    """
    cluster_manager = load_cluster_manager(cluster_config)
    if policy_packs:
        cluster_manager.preview(policy_packs=policy_packs)
    else:
        cluster_manager.preview()

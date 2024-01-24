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
        help="Path to the cluster config file.",
    ),
    update_kubeconfig: bool = typer.Option(
        False,
        "--update-kubeconfig",
        "-u",
        help="Update kubeconfig with the new cluster.",
    ),
) -> None:
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
        help="Path to the cluster config file.",
    ),
) -> None:
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.destroy()


@cluster_app.command()
def refresh(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file.",
    ),
) -> None:
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.refresh()


@cluster_app.command()
def preview(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file.",
    ),
    policy_pack: str = typer.Option(
        "",
        "--policy-pack",
        "-p",
        help="Path to the policy pack.",
    ),
) -> None:
    cluster_manager = load_cluster_manager(cluster_config)
    if policy_pack:
        cluster_manager.preview(policy_packs=[policy_pack])
    else:
        cluster_manager.preview()

import typer

from light.k8s import update_kubeconfig
from light.logger import logger

kube_app = typer.Typer()


@kube_app.command(help="Update the kubeconfig file for kubectl.")
def update() -> None:
    logger.info("Updating kubeconfig...")
    update_kubeconfig()
    logger.info("Successfully updated kubeconfig.")

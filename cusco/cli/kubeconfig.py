import typer

from cusco.k8s import update_kubeconfig
from cusco.logger import logger

kube_app = typer.Typer()


@kube_app.command()
def update() -> None:
    """
    Updates the default kubeconfig file (~/.kube/config) to include the connection
    details of the newly provisioned Kubernetes cluster
    """
    logger.info("Updating kubeconfig...")
    update_kubeconfig()
    logger.info("Successfully updated kubeconfig.")

from __future__ import annotations

import json
import os
from typing import Optional

import typer

from paka.cli.utils import ensure_cluster_name
from paka.k8s.utils import update_kubeconfig
from paka.logger import logger
from paka.utils import read_pulumi_stack

kube_app = typer.Typer()


@kube_app.command()
def update(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    )
) -> None:
    """
    Updates the default kubeconfig file (~/.kube/config) to include the connection
    details of the specified cluster.
    """
    logger.info("Updating kubeconfig...")
    cluster_name = ensure_cluster_name(cluster_name)
    kubeconfig = read_pulumi_stack(cluster_name, "kubeconfig")

    update_kubeconfig(json.loads(kubeconfig))
    logger.info("Successfully updated kubeconfig.")

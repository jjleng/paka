from __future__ import annotations

import os
from typing import Optional, Set

import boto3
import typer
from kubernetes import client
from tabulate import tabulate

from paka.cli.utils import (
    ensure_cluster_name,
    get_cluster_namespace,
    load_kubeconfig,
    read_pulumi_stack,
)
from paka.k8s.model_group.service import MODEL_PATH_PREFIX, filter_services
from paka.logger import logger

model_group_app = typer.Typer()


@model_group_app.command()
def list_downloaded_models(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
) -> None:
    """
    List all models that have been downloaded to the object store.
    """
    load_kubeconfig(cluster_name)
    cluster_name = ensure_cluster_name(cluster_name)
    bucket = read_pulumi_stack(cluster_name, "bucket")

    s3 = boto3.client("s3")
    response = s3.list_objects_v2(Bucket=bucket, Prefix=MODEL_PATH_PREFIX)
    if "Contents" in response:
        unique_models: Set[str] = set()
        for obj in response["Contents"]:
            key = obj["Key"]
            if key.startswith(f"{MODEL_PATH_PREFIX}/"):
                key = key[len(f"{MODEL_PATH_PREFIX}/") :]

            key = key.split("/")[0]
            unique_models.add(key)

        for key in unique_models:
            logger.info(key)
    else:
        logger.info("No models found.")


@model_group_app.command()
def list(
    cluster_name: Optional[str] = typer.Option(
        os.getenv("PAKA_CURRENT_CLUSTER"),
        "--cluster",
        "-c",
        help="The name of the cluster.",
    ),
) -> None:
    """
    List all model groups.
    """
    load_kubeconfig(cluster_name)
    services = filter_services(get_cluster_namespace(cluster_name))
    model_groups = [
        service.spec.selector.get("model", "")
        for service in services
        if service.spec and service.spec.selector and "model" in service.spec.selector
    ]

    v1 = client.CoreV1Api()
    cfg = v1.read_namespaced_config_map("config-domain", "knative-serving")
    cfg_data = cfg.data or {}
    filtered_keys = [key for key in cfg_data if key.endswith("sslip.io")]
    if not filtered_keys:
        if not model_groups:
            logger.info("No model groups found.")
        else:
            logger.info("\n".join(model_groups))
        return
    domain = filtered_keys[0]

    table = [(group, f"http://{group}.{domain}") for group in model_groups]
    logger.info(tabulate(table, headers=["Model Group", "Endpoint"]))

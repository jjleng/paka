from typing import Set

import boto3
import typer
from kubernetes import client
from tabulate import tabulate

from light.constants import APP_NS
from light.k8s import try_load_kubeconfig
from light.kube_resources.model_group.model import SUPPORTED_MODELS
from light.kube_resources.model_group.service import MODEL_PATH_PREFIX, filter_services
from light.logger import logger
from light.utils import read_current_cluster_data

try_load_kubeconfig()

model_group_app = typer.Typer()


@model_group_app.command(help="List available models.")
def list_all_models() -> None:
    for model_name in SUPPORTED_MODELS:
        logger.info(model_name)


@model_group_app.command(help="List the models downloaded to object store.")
def list_downloaded_models() -> None:
    bucket = read_current_cluster_data("bucket")
    s3 = boto3.client("s3")
    response = s3.list_objects_v2(Bucket=bucket, Prefix=MODEL_PATH_PREFIX)
    if "Contents" in response:
        unique_models: Set[str] = set()
        for obj in response["Contents"]:
            key = obj["Key"]
            if key.startswith(f"{MODEL_PATH_PREFIX}/"):
                key = key[len(f"{MODEL_PATH_PREFIX}/") :]

            key = key.split("/")[0]
            if key in SUPPORTED_MODELS:
                unique_models.add(key)

        for key in unique_models:
            logger.info(key)
    else:
        logger.info("No models found.")


@model_group_app.command(help="List model groups.")
def list() -> None:
    services = filter_services(APP_NS)
    model_groups = [service.spec.selector.get("model") for service in services]

    v1 = client.CoreV1Api()
    cfg = v1.read_namespaced_config_map("config-domain", "knative-serving")
    filtered_keys = [key for key in cfg.data.keys() if key.endswith("sslip.io")]
    if not filtered_keys:
        if not model_groups:
            logger.info("No model groups found.")
        else:
            logger.info("\n".join(model_groups))
        return
    domain = filtered_keys[0]

    table = [(group, f"{group}.{domain}") for group in model_groups]
    logger.info(tabulate(table, headers=["Model Group", "Endpoint"]))

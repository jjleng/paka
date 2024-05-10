from __future__ import annotations

import json
from typing import Optional

import boto3
from kubernetes import client, config


# Pulumi cannot update the idle timeout of an ELB. This script uses boto3 to
# update the idle timeout of an ELB.
def _update_elb_idle_timeout(
    load_balancer_name: str, idle_timeout_seconds: int
) -> None:
    elb_client = boto3.client("elb")

    attributes = {
        "LoadBalancerAttributes": {
            "ConnectionSettings": {"IdleTimeout": idle_timeout_seconds}
        }
    }

    elb_client.modify_load_balancer_attributes(
        LoadBalancerName=load_balancer_name,
        LoadBalancerAttributes=attributes["LoadBalancerAttributes"],
    )


def update_elb_idle_timeout(kubeconfig_json: str, idle_timeout_seconds: int) -> None:
    elb_name = get_elb_name(kubeconfig_json)

    if elb_name:
        _update_elb_idle_timeout(elb_name, idle_timeout_seconds)


def get_elb_name(kubeconfig_json: str) -> Optional[str]:
    config.load_kube_config_from_dict(json.loads(kubeconfig_json))

    v1 = client.CoreV1Api()
    services = v1.list_service_for_all_namespaces(watch=False)

    for service in services.items:
        if service.spec and service.spec.type == "LoadBalancer":
            # The name of the ELB is the first part of the hostname of the load balancer
            if (
                service.status
                and service.status.load_balancer
                and service.status.load_balancer.ingress
            ):
                elb_hostname = service.status.load_balancer.ingress[0].hostname
                if not elb_hostname:
                    continue
                elb_name = elb_hostname.split("-")[0]
                return elb_name

    return None

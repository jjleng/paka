from typing import List

from kubernetes import client

from paka.k8s import CustomResource, apply_resource
from paka.utils import kubify_name


def create_model_group_ingress(namespace: str) -> None:
    istio_gateway_crd = CustomResource(
        api_version="networking.istio.io/v1beta1",
        kind="Gateway",
        plural="gateways",
        metadata=client.V1ObjectMeta(
            name="model-group-ingress-gateway", namespace=namespace
        ),
        spec={
            "selector": {
                "istio": "ingressgateway"  # Use Istio's default ingress gateway
            },
            "servers": [
                {
                    "port": {"number": 80, "name": "http", "protocol": "HTTP"},
                    "hosts": ["*"],
                }
            ],
        },
    )

    apply_resource(istio_gateway_crd)


def create_model_vservice(
    namespace: str, model_name: str, hosts: List[str] = ["*"]
) -> None:
    istio_virtual_service = CustomResource(
        api_version="networking.istio.io/v1beta1",
        kind="VirtualService",
        plural="virtualservices",
        metadata=client.V1ObjectMeta(name=kubify_name(model_name), namespace=namespace),
        spec={
            "hosts": hosts,
            "gateways": ["model-group-ingress-gateway"],
            "http": [
                {
                    "match": [
                        {
                            "authority": {
                                "prefix": kubify_name(model_name),
                            }
                        }
                    ],
                    "route": [
                        {
                            "destination": {
                                "host": f"{kubify_name(model_name)}.{namespace}.svc.cluster.local",
                                "port": {"number": 80},
                            }
                        }
                    ],
                }
            ],
        },
    )

    apply_resource(istio_virtual_service)

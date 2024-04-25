from __future__ import annotations

from typing import List

from kubernetes import client

from paka.k8s.utils import CustomResource, apply_resource
from paka.utils import kubify_name


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
            "gateways": ["knative-serving/knative-ingress-gateway"],
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

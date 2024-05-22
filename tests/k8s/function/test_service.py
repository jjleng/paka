from unittest.mock import MagicMock, patch

import pytest

import paka.k8s.function.service
from paka.k8s.function.service import create_knative_service, validate_resource


def test_create_knative_service() -> None:
    with patch.object(
        paka.k8s.function.service.client, "ApiClient"
    ) as mock_api_client, patch.object(
        paka.k8s.function.service, "DynamicClient"
    ) as mock_dynamic_client, patch.object(
        paka.k8s.function.service, "apply_resource"
    ):

        mock_service_resource = MagicMock()
        mock_dynamic_client.resources.get.return_value = mock_service_resource
        mock_api_client.return_value = mock_dynamic_client

        with pytest.raises(
            ValueError, match="min_replicas cannot be greater than max_replicas"
        ):
            create_knative_service(
                service_name="test-service",
                namespace="test-namespace",
                image="test-image",
                entrypoint="test-entrypoint",
                min_instances=3,
                max_instances=1,
                scaling_metric=("concurrency", "10"),
                scale_down_delay="0s",
            )

        with pytest.raises(ValueError, match="Invalid key in scaling_metric"):
            create_knative_service(
                service_name="test-service",
                namespace="test-namespace",
                image="test-image",
                entrypoint="test-entrypoint",
                min_instances=1,
                max_instances=3,
                scaling_metric=("invalid", "10"),  # type: ignore
                scale_down_delay="0s",
            )

        with pytest.raises(ValueError, match="Invalid value in scaling_metric"):
            create_knative_service(
                service_name="test-service",
                namespace="test-namespace",
                image="test-image",
                entrypoint="test-entrypoint",
                min_instances=1,
                max_instances=3,
                scaling_metric=("concurrency", "invalid"),
                scale_down_delay="0s",
            )

        with pytest.raises(ValueError, match="Invalid resource request key"):
            create_knative_service(
                service_name="test-service",
                namespace="test-namespace",
                image="test-image",
                entrypoint="test-entrypoint",
                min_instances=1,
                max_instances=3,
                scaling_metric=("concurrency", "10"),
                scale_down_delay="0s",
                resource_requests={"invalid": "100m"},
            )

        with pytest.raises(ValueError, match="Invalid resource limit key"):
            create_knative_service(
                service_name="test-service",
                namespace="test-namespace",
                image="test-image",
                entrypoint="test-entrypoint",
                min_instances=1,
                max_instances=3,
                scaling_metric=("concurrency", "10"),
                scale_down_delay="0s",
                resource_limits={"invalid": "100m"},
            )
        service = create_knative_service(
            service_name="test-service",
            namespace="test-namespace",
            image="test-image",
            entrypoint="test-entrypoint",
            min_instances=1,
            max_instances=3,
            scaling_metric=("concurrency", "10"),
            scale_down_delay="0s",
            envs={
                "ENV_VAR_NAME_1": "ENV_VAR_VALUE_1",
                "ENV_VAR_NAME_2": "ENV_VAR_VALUE_2",
            },
        )

        envs = service["spec"]["template"]["spec"]["containers"][0]["env"]
        assert len(envs) == 2
        assert {"name": "ENV_VAR_NAME_1", "value": "ENV_VAR_VALUE_1"} in envs
        assert {"name": "ENV_VAR_NAME_2", "value": "ENV_VAR_VALUE_2"} in envs


def test_validate_resource_cpu() -> None:
    validate_resource("cpu", "100m")
    validate_resource("cpu", "1")

    with pytest.raises(ValueError, match="Invalid CPU value"):
        validate_resource("cpu", "100k")
    with pytest.raises(ValueError, match="Invalid CPU value"):
        validate_resource("cpu", "abc")


def test_validate_resource_memory() -> None:
    validate_resource("memory", "128Mi")
    validate_resource("memory", "1Gi")

    with pytest.raises(ValueError, match="Invalid memory value"):
        validate_resource("memory", "128Ki")
    with pytest.raises(ValueError, match="Invalid memory value"):
        validate_resource("memory", "abc")


def test_validate_resource_gpu() -> None:
    validate_resource("nvidia.com/gpu", "1")

    with pytest.raises(ValueError, match="Invalid GPU value"):
        validate_resource("nvidia.com/gpu", "0")
    with pytest.raises(ValueError, match="Invalid GPU value"):
        validate_resource("nvidia.com/gpu", "abc")

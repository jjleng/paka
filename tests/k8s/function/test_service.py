from unittest.mock import MagicMock, patch

import pytest

import paka.k8s.function.service
from paka.k8s.function.service import create_knative_service, validate_resource


def test_create_knative_service() -> None:
    with patch.object(
        paka.k8s.function.service.client, "ApiClient"
    ) as mock_api_client, patch.object(
        paka.k8s.function.service, "DynamicClient"
    ) as mock_dynamic_client:

        mock_service_resource = MagicMock()
        mock_dynamic_client.resources.get.return_value = mock_service_resource
        mock_api_client.return_value = mock_dynamic_client

        with pytest.raises(
            ValueError, match="min_replicas cannot be greater than max_replicas"
        ):
            create_knative_service(
                "test-service",
                "test-namespace",
                "test-image",
                "test-entrypoint",
                3,
                1,
                ("concurrency", "10"),
                "0s",
            )

        with pytest.raises(ValueError, match="Invalid key in scaling_metric"):
            create_knative_service(
                "test-service",
                "test-namespace",
                "test-image",
                "test-entrypoint",
                1,
                3,
                ("invalid", "10"),  # type: ignore
                "0s",
            )

        with pytest.raises(ValueError, match="Invalid value in scaling_metric"):
            create_knative_service(
                "test-service",
                "test-namespace",
                "test-image",
                "test-entrypoint",
                1,
                3,
                ("concurrency", "invalid"),
                "0s",
            )

        with pytest.raises(ValueError, match="Invalid resource request key"):
            create_knative_service(
                "test-service",
                "test-namespace",
                "test-image",
                "test-entrypoint",
                1,
                3,
                ("concurrency", "10"),
                "0s",
                {"invalid": "100m"},
            )

        with pytest.raises(ValueError, match="Invalid resource limit key"):
            create_knative_service(
                "test-service",
                "test-namespace",
                "test-image",
                "test-entrypoint",
                1,
                3,
                ("concurrency", "10"),
                "0s",
                None,
                {"invalid": "100m"},
            )


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

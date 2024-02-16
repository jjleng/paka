from unittest.mock import MagicMock, patch

from kubernetes.client.rest import ApiException

from paca.k8s import KubeconfigMerger, KubernetesResource, apply_resource


def test_apply_resource() -> None:
    resource = MagicMock(spec=KubernetesResource)
    resource.kind = "Deployment"
    resource.metadata = MagicMock()
    resource.metadata.name = "test"
    resource.metadata.namespace = "default"

    with patch("kubernetes.client.AppsV1Api") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.create_namespaced_deployment = MagicMock()
        mock_api.replace_namespaced_deployment = MagicMock()
        mock_api.read_namespaced_deployment = MagicMock(
            side_effect=ApiException(status=404)
        )

        apply_resource(resource)

        mock_api.create_namespaced_deployment.assert_called_once_with(
            resource.metadata.namespace, resource
        )


def test_apply_resource_existing() -> None:
    resource = MagicMock(spec=KubernetesResource)
    resource.kind = "Deployment"
    resource.metadata = MagicMock()
    resource.metadata.name = "test"
    resource.metadata.namespace = "default"

    with patch("kubernetes.client.AppsV1Api") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.create_namespaced_deployment = MagicMock()
        mock_api.replace_namespaced_deployment = MagicMock()
        mock_api.read_namespaced_deployment = MagicMock()

        apply_resource(resource)

        mock_api.replace_namespaced_deployment.assert_called_once_with(
            resource.metadata.name, resource.metadata.namespace, resource
        )


def test_apply_resource_scaled_object() -> None:
    resource = MagicMock()
    resource.kind = "ScaledObject"
    resource.metadata = MagicMock()
    resource.metadata.name = "test"
    resource.metadata.namespace = "default"

    with patch("paca.k8s.create_namespaced_custom_object") as mock_create, patch(
        "paca.k8s.read_namespaced_custom_object"
    ) as mock_read:
        mock_read.side_effect = ApiException(status=404)

        apply_resource(resource)

        mock_create.assert_called_once_with(resource.metadata.namespace, resource)


def test_kubeconfig_merger() -> None:
    # Initialize a KubeconfigMerger object with some initial config
    merger = KubeconfigMerger(
        {
            "clusters": [{"name": "cluster1", "data": "data1"}],
            "users": [{"name": "user1", "data": "data1"}],
            "contexts": [{"name": "context1", "data": "data1"}],
            "current-context": "context1",
            "other-key": "other-value",
        }
    )

    # Define a new config to be merged
    new_config = {
        "clusters": [{"name": "cluster2", "data": "data2"}],
        "users": [{"name": "user2", "data": "data2"}],
        "contexts": [{"name": "context2", "data": "data2"}],
        "current-context": "context2",
        "other-key": "other-value2",
    }

    merger.merge(new_config)

    assert merger.config == {
        "clusters": [
            {"name": "cluster1", "data": "data1"},
            {"name": "cluster2", "data": "data2"},
        ],
        "users": [
            {"name": "user1", "data": "data1"},
            {"name": "user2", "data": "data2"},
        ],
        "contexts": [
            {"name": "context1", "data": "data1"},
            {"name": "context2", "data": "data2"},
        ],
        "current-context": "context2",
        "other-key": "other-value2",
    }

import os
from unittest.mock import MagicMock, mock_open, patch

import click
import pytest

from light.cli.utils import (
    init_pulumi,
    load_cluster_manager,
    resolve_image,
    validate_name,
)
from light.cluster.manager.aws import AWSClusterManager


def test_resolve_image() -> None:
    with patch("os.path.abspath") as mock_abspath, patch(
        "os.path.expanduser"
    ) as mock_expanduser, patch("os.path.basename") as mock_basename, patch(
        "light.cli.utils.build"
    ) as mock_build, patch(
        "light.cli.utils.read_current_cluster_data"
    ) as mock_read_current_cluster_data:
        mock_abspath.return_value = "/absolute/path/to/source_dir"
        mock_expanduser.return_value = "/path/to/source_dir"
        mock_basename.return_value = "source_dir"
        mock_build.return_value = None
        mock_read_current_cluster_data.return_value = "registry_uri"

        result = resolve_image(None, "source_dir")
        assert result == "registry_uri:source_dir-latest"

        # Test case when image is provided and source_dir is None
        result = resolve_image("image", None)
        assert result == "registry_uri:image"

        # Test case when a fully qualified image is provided
        result = resolve_image("fully/qualified/image:tag", None)
        assert result == "fully/qualified/image:tag"

        # Test case when neither image nor source_dir is provided
        with pytest.raises(click.exceptions.Exit):
            resolve_image(None, None)

        # Test case when both image and source_dir are provided
        with pytest.raises(click.exceptions.Exit):
            resolve_image("image", "source_dir")


def test_validate_name() -> None:
    mock_func = MagicMock()

    decorated_func = validate_name(mock_func)

    # Test case when name is valid
    decorated_func("valid-name")
    mock_func.assert_called_once_with("valid-name")

    mock_func.reset_mock()

    # Test case when name is not valid
    with pytest.raises(click.exceptions.Exit):
        decorated_func("Invalid-Name")
    mock_func.assert_not_called()

    mock_func.reset_mock()

    # Test case when name is too long
    with pytest.raises(click.exceptions.Exit):
        decorated_func("a" * 64)
    mock_func.assert_not_called()


def test_init_pulumi() -> None:
    with patch.dict(
        os.environ,
        {
            "PULUMI_CONFIG_PASSPHRASE": "test_passphrase",
            "PULUMI_BACKEND_URL": "test_backend_url",
        },
    ), patch("os.makedirs") as mock_makedirs:
        init_pulumi()

        assert os.environ["PULUMI_CONFIG_PASSPHRASE"] == "test_passphrase"
        assert os.environ["PULUMI_BACKEND_URL"] == "test_backend_url"

        mock_makedirs.assert_called_once()


def test_load_cluster_manager() -> None:
    cluster_config = "/path/to/cluster.yaml"
    config_data = {"aws": {"cluster": {"name": "test-cluster", "region": "us-west-2"}}}
    m = mock_open(
        read_data="aws:\n  cluster:\n    name: test-cluster\n    region: us-west-2"
    )

    with patch("os.path.abspath", return_value=cluster_config), patch(
        "os.path.expanduser", return_value=cluster_config
    ), patch("os.path.exists", return_value=True), patch("builtins.open", m), patch(
        "light.config.parse_yaml", return_value=config_data
    ):
        result = load_cluster_manager(cluster_config)

    m.assert_called_once_with(cluster_config, "r")
    assert isinstance(result, AWSClusterManager)
    assert result.config.model_dump(exclude_none=True) == config_data["aws"]

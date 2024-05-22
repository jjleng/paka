import os
from datetime import timedelta
from unittest.mock import MagicMock, mock_open, patch

import click
import pytest

import paka.cli.utils
import paka.config
from paka.cli.utils import (
    format_timedelta,
    init_pulumi,
    load_cluster_manager,
    process_envs,
    resolve_image,
    validate_name,
)
from paka.cluster.manager.aws import AWSClusterManager


def test_resolve_image() -> None:
    with patch("os.path.abspath") as mock_abspath, patch(
        "os.path.expanduser"
    ) as mock_expanduser, patch("os.path.basename") as mock_basename, patch.object(
        paka.cli.utils, "build_and_push"
    ) as mock_build_and_push, patch.object(
        paka.cli.utils, "read_pulumi_stack"
    ) as mock_read_pulumi_stack, patch.object(
        paka.cli.utils, "ensure_cluster_name"
    ) as mock_ensure_cluster_name:
        mock_abspath.return_value = "/absolute/path/to/source_dir"
        mock_expanduser.return_value = "/path/to/source_dir"
        mock_basename.return_value = "source_dir"
        mock_build_and_push.return_value = "source_dir-abc"
        mock_read_pulumi_stack.return_value = "registry_uri"
        mock_ensure_cluster_name.return_value = "cluster_name"

        result = resolve_image("cluster_name", None, "source_dir")
        assert result == "registry_uri:source_dir-abc"

        # Test case when image is provided and source_dir is None
        result = resolve_image("cluster_name", "image", None)
        assert result == "registry_uri:image"

        # Test case when a fully qualified image is provided
        result = resolve_image("cluster_name", "fully/qualified/image:tag", None)
        assert result == "fully/qualified/image:tag"

        # Test case when neither image nor source_dir is provided
        with pytest.raises(click.exceptions.Exit):
            resolve_image("cluster_name", None, None)

        # Test case when both image and source_dir are provided
        with pytest.raises(click.exceptions.Exit):
            resolve_image("cluster_name", "image", "source_dir")


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
    config_data = {
        "version": "1.0",
        "aws": {
            "cluster": {
                "name": "test-cluster",
                "region": "us-west-2",
                "namespace": "test-namespace",
                "nodeType": "t2.medium",
                "minNodes": 2,
                "maxNodes": 4,
                "logRetentionDays": 7,
            }
        },
    }
    m = mock_open(read_data="""
        version: "1.0"
        aws:
          cluster:
            name: test-cluster
            region: us-west-2
            namespace: test-namespace
            nodeType: t2.medium
            minNodes: 2
            maxNodes: 4
            logRetentionDays: 7
        """)

    with patch("os.path.abspath", return_value=cluster_config), patch(
        "os.path.expanduser", return_value=cluster_config
    ), patch("os.path.exists", return_value=True), patch(
        "builtins.open", m
    ), patch.object(
        paka.config, "parse_yaml", return_value=config_data
    ), patch(
        "os.makedirs"
    ):
        result = load_cluster_manager(cluster_config)

    assert isinstance(result, AWSClusterManager)
    assert result.cloud_config.model_dump(exclude_none=True) == config_data["aws"]


def test_format_timedelta() -> None:
    assert format_timedelta(timedelta(days=1, hours=2)) == "1d2h"
    assert format_timedelta(timedelta(hours=2, minutes=30)) == "2h30m"
    assert format_timedelta(timedelta(minutes=30, seconds=45)) == "30m45s"
    assert format_timedelta(timedelta(seconds=45)) == "45s"


def test_process_envs() -> None:
    assert process_envs(["A=B", "C=D"]) == {"A": "B", "C": "D"}
    assert process_envs(["A=B,C=D"]) == {"A": "B", "C": "D"}
    assert process_envs(["A=B,C=D", "E=F"]) == {"A": "B", "C": "D", "E": "F"}
    assert process_envs([]) == {}

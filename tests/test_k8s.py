from light.k8s import (
    save_kubeconfig,
)
from light.utils import get_project_data_dir
import json
import os
from unittest.mock import mock_open, patch


def test_save_kubeconfig() -> None:
    m = mock_open()
    with patch("builtins.open", m):
        kubeconfig_json = json.dumps({"apiVersion": "v1"})
        save_kubeconfig("test", kubeconfig_json)
    f = os.path.join(get_project_data_dir(), "test")
    m.assert_called_once_with(f, "w")
    handle = m()
    handle.write.assert_called_once()

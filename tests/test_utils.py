from light.utils import camel_to_kebab, save_kubeconfig, get_project_data_dir
import json
import os
from unittest.mock import mock_open, patch


def test_camel_to_kebab() -> None:
    assert camel_to_kebab("ExampleProject") == "example-project"
    assert camel_to_kebab("AnotherExampleProject") == "another-example-project"
    assert camel_to_kebab("YetAnotherExample") == "yet-another-example"
    assert camel_to_kebab("lowercase") == "lowercase"
    assert camel_to_kebab("UPPERCASE") == "uppercase"


def test_save_kubeconfig() -> None:
    m = mock_open()
    with patch("builtins.open", m):
        kubeconfig_json = json.dumps({"apiVersion": "v1"})
        save_kubeconfig("test", kubeconfig_json)
    f = os.path.join(get_project_data_dir(), "test")
    m.assert_called_once_with(f, "w")
    handle = m()
    handle.write.assert_called_once()

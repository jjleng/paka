import json
import os
from pathlib import Path
from unittest.mock import mock_open, patch

from paka.constants import HOME_ENV_VAR, PROJECT_NAME
from paka.utils import (
    call_once,
    camel_to_kebab,
    camel_to_snake,
    get_cluster_data_dir,
    get_project_data_dir,
    kubify_name,
    save_kubeconfig,
    to_yaml,
)


def test_camel_to_kebab() -> None:
    assert camel_to_kebab("ExampleProject") == "example-project"
    assert camel_to_kebab("AnotherExampleProject") == "another-example-project"
    assert camel_to_kebab("YetAnotherExample") == "yet-another-example"
    assert camel_to_kebab("lowercase") == "lowercase"
    assert camel_to_kebab("UPPERCASE") == "uppercase"


def test_kubify_name() -> None:
    assert kubify_name("MyName") == "myname"
    assert kubify_name("My.Name") == "my-name"
    assert kubify_name("My_Name") == "my-name"
    assert kubify_name("My-Name") == "my-name"
    assert kubify_name("123MyName") == "myname"
    assert kubify_name("MyName123") == "myname123"
    assert kubify_name("MyName!") == "myname"


def test_call_once() -> None:
    counter = 0

    @call_once
    def increment_counter() -> None:
        nonlocal counter
        counter += 1

    # Call the function twice
    increment_counter()
    increment_counter()

    # Check that the counter was only incremented once
    assert counter == 1


def test_to_yaml() -> None:
    obj = {"key": "value"}
    yaml_str = to_yaml(obj)
    assert yaml_str == "key: value\n"

    obj1 = {"key": {"nested_key": "nested_value"}}
    yaml_str = to_yaml(obj1)
    assert yaml_str == "key:\n  nested_key: nested_value\n"

    obj2 = {"key": ["value1", "value2"]}
    yaml_str = to_yaml(obj2)
    assert yaml_str == "key:\n  - value1\n  - value2\n"


def test_save_kubeconfig() -> None:
    m = mock_open()
    # Replace the built-in open function with the mock object
    with patch("builtins.open", m):
        kubeconfig_json = json.dumps({"apiVersion": "v1"})
        save_kubeconfig("test", kubeconfig_json)
    f = os.path.join(get_cluster_data_dir("test"), "kubeconfig.yaml")
    m.assert_called_once_with(f, "w")
    handle = m()
    handle.write.assert_called_once()


def test_get_project_data_dir() -> None:
    with patch.dict(os.environ, {HOME_ENV_VAR: "/test/home"}):
        result = get_project_data_dir()

        assert result == "/test/home"

    with patch.dict(os.environ, {}, clear=True):
        result = get_project_data_dir()

        assert result == os.path.join(
            str(Path.home()), f".{camel_to_kebab(PROJECT_NAME)}"
        )


def test_camel_to_snake() -> None:
    assert camel_to_snake("camelCase") == "camel_case"
    assert camel_to_snake("HTTPRequest") == "http_request"
    assert camel_to_snake("IPV6Address") == "ipv6_address"
    assert camel_to_snake("noChange") == "no_change"
    assert camel_to_snake("") == ""

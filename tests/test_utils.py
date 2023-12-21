from light.utils import (
    camel_to_kebab,
    get_project_data_dir,
    sanitize_k8s_name,
    call_once,
)


def test_camel_to_kebab() -> None:
    assert camel_to_kebab("ExampleProject") == "example-project"
    assert camel_to_kebab("AnotherExampleProject") == "another-example-project"
    assert camel_to_kebab("YetAnotherExample") == "yet-another-example"
    assert camel_to_kebab("lowercase") == "lowercase"
    assert camel_to_kebab("UPPERCASE") == "uppercase"


def test_sanitize_k8s_name() -> None:
    assert sanitize_k8s_name("MyName") == "myname"
    assert sanitize_k8s_name("My.Name") == "my-name"
    assert sanitize_k8s_name("My_Name") == "my-name"
    assert sanitize_k8s_name("My-Name") == "my-name"
    assert sanitize_k8s_name("123MyName") == "123myname"
    assert sanitize_k8s_name("MyName123") == "myname123"
    assert sanitize_k8s_name("MyName!") == "myname"


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

import os
from pathlib import Path
from light.constants import PROJECT_NAME
import re
from typing import Callable, Any


def camel_to_kebab(name: str) -> str:
    """
    Converts a camel case string to kebab case.

    Args:
        name (str): The camel case string to be converted.

    Returns:
        str: The kebab case string.

    Example:
        >>> camel_to_kebab("camelCaseString")
        'camel-case-string'
    """
    name = re.sub("(.)([A-Z][a-z]+)", r"\1-\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1-\2", name).lower()


def sanitize_k8s_name(name: str) -> str:
    """
    Sanitize a string to be compliant with Kubernetes resource naming conventions.

    Args:
    name (str): The original name string.

    Returns:
    str: The sanitized name string.
    """

    # Convert to lowercase
    sanitized_name = name.lower()

    # Replace any disallowed characters with '-'
    sanitized_name = re.sub(r"[^a-z0-9\-]", "-", sanitized_name)

    # Remove leading or trailing non-alphanumeric characters
    sanitized_name = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", sanitized_name)

    return sanitized_name


def get_project_data_dir() -> str:
    """
    Get the project data directory.

    Returns:
        str: The project data directory.
    """
    home = Path.home()
    return os.path.join(home, f".{camel_to_kebab(PROJECT_NAME)}")


def call_once(func: Callable) -> Callable:
    """Decorator to ensure a function is only called once."""
    has_been_called = False

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        nonlocal has_been_called
        if not has_been_called:
            has_been_called = True
            return func(*args, **kwargs)

    return wrapper

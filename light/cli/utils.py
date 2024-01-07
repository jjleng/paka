import functools
import re
from typing import Any, Tuple

import typer

from light.logger import logger


def validate_name(func: Any) -> Any:
    @functools.wraps(func)
    def wrapper(name: str, *args: Any, **kwargs: Any) -> Any:
        if (
            not re.match(
                r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                name,
            )
            or len(name) > 63
        ):
            logger.info(
                "Invalid name. It must contain no more than 63 characters, contain only lowercase alphanumeric characters or '-', start with an alphanumeric character, and end with an alphanumeric character."
            )
            raise typer.Exit(1)
        return func(name, *args, **kwargs)

    return wrapper


def pick_runtime(runtime: str) -> Tuple[str, str]:
    language, version = runtime.split(":")
    if not language or not version:
        logger.info(
            "Invalid runtime. Runtime must be in the format of 'language:version'."
        )
        raise typer.Exit(1)

    if language not in ["python", "node"]:
        logger.info(
            f"Invalid language '{language}'. Supported languages are 'python' and 'node'."
        )
        raise typer.Exit(1)

    # Only support python for now
    if language != "python":
        logger.info(f"Invalid language '{language}'. Only 'python' is supported.")
        raise typer.Exit(1)

    # Only support version 3.11 for now
    if version not in ["3.11"]:
        logger.info(
            f"Invalid version '{version}'. Supported versions for language '{language}' are '3.11'."
        )
        raise typer.Exit(1)

    return (
        f"jijunleng/{language}-env-{version}:bookworm-slim",
        f"jijunleng/{language}-builder-{version}:bookworm-slim",
    )

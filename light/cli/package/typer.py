import typer
import tempfile
import os
import re
from light.cli.package.archive import archive_directory
from light.cli.package.ignore import blacklist


package_app = typer.Typer()


@package_app.command("create")
def package_create(
    name: str = typer.Argument(
        ...,
        help="The package name",
    ),
    source_directory: str = typer.Option(
        ...,
        "--source",
        "-s",
        help="The source directory to create the package from",
    ),
    env: str = typer.Option(
        ...,
        "--env",
        "-e",
        help="The environment to use for the package. Supported environments are 'python3.12', 'node18', etc.",
    ),
) -> None:
    if (
        not re.match(
            r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$", name
        )
        or len(name) > 63
    ):
        typer.echo(
            "Invalid package name. It must contain no more than 63 characters, contain only lowercase alphanumeric characters, '-' or '.', start with an alphanumeric character, and end with an alphanumeric character."
        )
        raise typer.Exit(1)

    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = os.path.join(temp_dir, name)
        typer.echo(
            f"Creating archive '{name}.zip' in temporary directory '{temp_dir}'..."
        )
        archive_directory(source_directory, archive_path, blacklist)
        typer.echo(f"Archive '{archive_path}.zip' created successfully.")

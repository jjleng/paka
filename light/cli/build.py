import typer

from light.cli.utils import build as build_image

build_app = typer.Typer()


@build_app.callback(invoke_without_command=True)
def build(
    source_dir: str = typer.Argument(
        ...,
        help="Source directory of the application.",
    ),
    image_name: str = typer.Option(
        "",
        "--image-name",
        help="The name for the Docker image that will be built.",
    ),
) -> None:
    build_image(source_dir, image_name)

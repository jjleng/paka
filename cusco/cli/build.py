import typer

from cusco.cli.utils import build as build_image

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
        help="Provide a custom name for the Docker image. If omitted, "
        "the base name of the source code directory will be used as the image name.",
    ),
) -> None:
    """
    Build a Docker image from the application in the specified source directory.
    The source directory must contain a Procfile and a .cnignore file. The Procfile
    defines the commands to run for the application. The .cnignore file defines the
    files and directories to exclude from the image. Once the image is built,
    it will be pushed to the container repository of the current cluster.

    A Dockerfile is NOT required. The image will be built using Cloud Native Buildpacks.
    In cluster build is not supported yet. User machine must have Docker installed.
    """
    build_image(source_dir, image_name)

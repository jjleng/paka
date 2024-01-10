import subprocess

import typer

from light.container.pack import install_pack
from light.logger import logger

build_app = typer.Typer()


@build_app.callback(invoke_without_command=True)
def build(
    source_dir: str = typer.Argument(
        ...,
        help="Source directory of the application.",
    ),
    image_name: str = typer.Option(
        ...,
        "--image-name",
        help="The name of the image to build.",
    ),
) -> None:
    # Install pack first
    install_pack()
    try:
        # Navigate to the application directory
        # (This step may be optional depending on your setup)
        subprocess.run(["cd", source_dir], check=True)

        # Build the application using pack
        subprocess.run(
            ["pack", "build", image_name, "--builder", "paketobuildpacks/builder:base"],
            check=True,
        )
        logger.info(f"Successfully built {image_name}")
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred: {e}")

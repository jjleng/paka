import typer

from light.cli.fission.archive import delete_archive, list_archive_files
from light.logger import logger

archive_app = typer.Typer()


@archive_app.command("list")
def archive_list() -> None:
    archives = list_archive_files()
    for archive in archives:
        logger.info(archive)


@archive_app.command("delete")
def archive_delete(
    archive_id: str = typer.Argument(
        ...,
        help="The archive id.",
    ),
) -> None:
    if not typer.confirm(
        "Are you sure you want to delete the archive files? You should delete packages and let the system prune the archive files for you."
    ):
        raise typer.Abort()

    delete_archive(archive_id)
    logger.info(f"Archive '{archive_id}' deleted successfully.")

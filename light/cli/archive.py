import typer
from light.logger import logger
from light.cli.fission.archive import list_archive_files, delete_archive


archive_app = typer.Typer()


@archive_app.command("list")
def archive_list() -> None:
    archives = list_archive_files("open-copilot")
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

    delete_archive("open-copilot", archive_id)
    logger.info(f"Archive '{archive_id}' deleted successfully.")

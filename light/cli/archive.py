import typer
from light.logger import logger
from light.cli.fission.archive import list_archive_files


archive_app = typer.Typer()


@archive_app.command("list")
def archive_list() -> None:
    archives = list_archive_files("open-copilot")
    for archive in archives:
        logger.info(archive)

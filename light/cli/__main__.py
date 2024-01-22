import typer

from light.cli.build import build_app
from light.cli.function import function_app
from light.cli.job import job_app
from light.cli.kubeconfig import kube_app
from light.cli.model_group import model_group_app
from light.cli.run import run_app
from light.cli.utils import load_cluster_manager
from light.k8s import update_kubeconfig as merge_update_kubeconfig
from light.logger import logger, setup_logger


def verbose_option(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
) -> None:
    setup_logger(verbose)


cli = typer.Typer()
cli.callback()(verbose_option)


cluster_app = typer.Typer()


@cluster_app.command()
def up(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file.",
    ),
    update_kubeconfig: bool = typer.Option(
        False,
        "--update-kubeconfig",
        "-u",
        help="Update kubeconfig with the new cluster.",
    ),
) -> None:
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.create()
    if update_kubeconfig:
        logger.info("Updating kubeconfig...")
        merge_update_kubeconfig()
        logger.info("Successfully updated kubeconfig.")


@cluster_app.command()
def down(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file.",
    ),
) -> None:
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.destroy()


@cluster_app.command()
def refresh(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file.",
    ),
) -> None:
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.refresh()


@cluster_app.command()
def preview(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file.",
    ),
) -> None:
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.preview()


cli.add_typer(cluster_app, name="cluster")

cli.add_typer(job_app, name="job")

cli.add_typer(build_app, name="build")

cli.add_typer(kube_app, name="kubeconfig")

cli.add_typer(run_app, name="run")

cli.add_typer(function_app, name="function")

cli.add_typer(model_group_app, name="model-group")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()

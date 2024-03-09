import typer

from paka import __version__
from paka.cli.build import build_app
from paka.cli.cluster import cluster_app
from paka.cli.function import function_app
from paka.cli.job import job_app
from paka.cli.kubeconfig import kube_app
from paka.cli.model_group import model_group_app
from paka.cli.run import run_app
from paka.cli.utils import init_pulumi
from paka.logger import setup_logger

init_pulumi()


def version_callback(version: bool) -> None:
    if version:
        typer.echo(f"Paka CLI Version: {__version__}")
        raise typer.Exit()


def verbose_option(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
) -> None:
    setup_logger(verbose)


cli = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})
cli.callback()(verbose_option)


@cli.callback()
def version_option(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", help="Show version and exit", callback=version_callback
    ),
) -> None:
    pass


cli.add_typer(cluster_app, name="cluster", help="Manage clusters.")

cli.add_typer(job_app, name="job", help="Manage batch jobs.")

cli.add_typer(build_app, name="build", help="Build Docker images.")

cli.add_typer(kube_app, name="kubeconfig", help="Export kubeconfig.")

cli.add_typer(run_app, name="run", help="Run one-off script.")

cli.add_typer(function_app, name="function", help="Manage serverless functions.")

cli.add_typer(model_group_app, name="model-group", help="Manage model groups.")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()

import typer

from light.cli.build import build_app
from light.cli.cluster import cluster_app
from light.cli.function import function_app
from light.cli.job import job_app
from light.cli.kubeconfig import kube_app
from light.cli.model_group import model_group_app
from light.cli.run import run_app
from light.logger import setup_logger


def verbose_option(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
) -> None:
    setup_logger(verbose)


cli = typer.Typer()
cli.callback()(verbose_option)

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

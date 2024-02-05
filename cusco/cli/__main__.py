import typer

from cusco.cli.build import build_app
from cusco.cli.cluster import cluster_app
from cusco.cli.function import function_app
from cusco.cli.job import job_app
from cusco.cli.kubeconfig import kube_app
from cusco.cli.model_group import model_group_app
from cusco.cli.run import run_app
from cusco.cli.utils import init_pulumi
from cusco.logger import setup_logger

init_pulumi()


def verbose_option(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
) -> None:
    setup_logger(verbose)


cli = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})
cli.callback()(verbose_option)

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

import typer

from light.cli.build import build_app
from light.cli.function import function_app
from light.cli.job import job_app
from light.cli.kubeconfig import kube_app
from light.cli.run import run_app
from light.cli.spec import spec_app
from light.cluster.manager.aws import AWSClusterManager
from light.config import CloudConfig, CloudModelGroup, ClusterConfig, Config
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

cluster_manager = AWSClusterManager(
    config=Config(
        aws=CloudConfig(
            cluster=ClusterConfig(name="lima", defaultRegion="us-west-2"),
            modelGroups=[
                CloudModelGroup(
                    name="llama-2-7b.Q4_0.gguf",
                    maxInstances=3,
                    minInstances=0,
                    nodeType="m5.xlarge",
                ),
            ],
        )
    )
)

cluster_app = typer.Typer()


@cluster_app.command()
def up(
    update_kubeconfig: bool = typer.Option(
        False,
        "--update-kubeconfig",
        "-u",
        help="Update kubeconfig with the new cluster.",
    ),
) -> None:
    cluster_manager.create()
    if update_kubeconfig:
        logger.info("Updating kubeconfig...")
        merge_update_kubeconfig()
        logger.info("Successfully updated kubeconfig.")


@cluster_app.command()
def down() -> None:
    cluster_manager.destroy()


@cluster_app.command()
def refresh() -> None:
    cluster_manager.refresh()


@cluster_app.command()
def preview() -> None:
    cluster_manager.preview()


cli.add_typer(cluster_app, name="cluster")


service_app = typer.Typer()


@service_app.command("up")
def service_up() -> None:
    cluster_manager.service_up()


cli.add_typer(service_app, name="service")

cli.add_typer(spec_app, name="spec")

cli.add_typer(job_app, name="job")

cli.add_typer(build_app, name="build")

cli.add_typer(kube_app, name="kubeconfig")

cli.add_typer(run_app, name="run")

cli.add_typer(function_app, name="function")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()

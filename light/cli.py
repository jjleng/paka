import typer
from light.cluster.manager.aws import AWSClusterManager
from light.config import CloudConfig, ClusterConfig, Config, CloudModelGroup

cli = typer.Typer()

cluster_manager = AWSClusterManager(
    config=Config(
        aws=CloudConfig(
            cluster=ClusterConfig(name="open-copilot", defaultRegion="us-west-2"),
            modelGroups=[
                CloudModelGroup(
                    name="llama-2-7b.Q4_0.gguf",
                    maxInstances=2,
                    minInstances=0,
                    nodeType="m5.xlarge",
                ),
            ],
        )
    )
)


@cli.command()
def create_cluster() -> None:
    cluster_manager.create()


@cli.command()
def destroy_cluster() -> None:
    cluster_manager.destroy()


@cli.command()
def refresh_cluster() -> None:
    cluster_manager.refresh()


@cli.command()
def preview_cluster() -> None:
    cluster_manager.preview()


@cli.command()
def service_up() -> None:
    cluster_manager.service_up()


if __name__ == "__main__":
    cli()

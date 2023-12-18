import typer
from light.cluster.manager.aws import AWSClusterManager
from light.cluster.config import CloudConfig, ClusterConfig, Config

cli = typer.Typer()

cluster_manager = AWSClusterManager(
    config=Config(
        aws=CloudConfig(
            cluster=ClusterConfig(name="open-copilot", defaultRegion="us-west-2")
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


if __name__ == "__main__":
    cli()

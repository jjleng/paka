import typer
from light.cluster.manager.aws import AWSClusterManager
from light.cluster.manager.config import CloudConfig, ClusterConfig, Config

cli = typer.Typer()

cluster_manager = AWSClusterManager(
    config=Config(
        aws=CloudConfig(cluster=ClusterConfig(name="test", defaultRegion="us-west-2"))
    )
)


@cli.command()
def create_cluster() -> None:
    cluster_manager.create()


@cli.command()
def destroy_cluster() -> None:
    cluster_manager.destroy()


if __name__ == "__main__":
    cli()

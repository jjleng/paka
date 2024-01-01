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

cluster_app = typer.Typer()


@cluster_app.command()
def up() -> None:
    cluster_manager.create()


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


if __name__ == "__main__":
    cli()

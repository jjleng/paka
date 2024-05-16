from __future__ import annotations

import threading
import time
from typing import List

import typer

from paka.cli.utils import load_cluster_manager, load_kubeconfig
from paka.k8s.utils import remove_crd_finalizers

cluster_app = typer.Typer()


@cluster_app.command()
def up(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file. The cluster config file is a "
        "YAML file that contains the configuration of the cluster",
    ),
    no_kubeconfig: bool = typer.Option(
        False,
        "--no-kubeconfig",
        "-n",
        help="By default, the connection details of the newly created Kubernetes "
        "cluster are added to the default kubeconfig file (~/.kube/config). "
        "This allows kubectl to communicate with the new cluster. "
        "Use this option to prevent updating the kubeconfig file.",
    ),
) -> None:
    """
    Creates or updates a Kubernetes cluster based on the provided configuration.
    """
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.ctx.set_should_save_kubeconfig(not no_kubeconfig)
    cluster_manager.create()


@cluster_app.command()
def down(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file. The cluster config file is a "
        "YAML file that contains the configuration of the cluster",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatic yes to prompts. Use this option to bypass the confirmation "
        "prompt and directly proceed with the operation.",
    ),
) -> None:
    """
    Tears down the Kubernetes cluster, removing all associated resources and data.
    """
    if yes or typer.confirm(
        f"Are you sure you want to proceed with the operation? Please note that "
        "all resources and data will be permanently deleted.",
        default=False,
    ):
        cluster_manager = load_cluster_manager(cluster_config)

        # Sometime finalizers might block CRD deletion, so we need to force delete those.
        # This is best effort and might not work in all cases.
        # TODO: better way to handle this
        # https://github.com/kubernetes/kubernetes/issues/60538
        stop_event = threading.Event()

        def remove_finalizers_forever() -> None:
            try:
                crds = [
                    "scaledobjects.keda.sh",
                    "routes.serving.knative.dev",
                    "ingresses.networking.internal.knative.dev",
                ]

                load_kubeconfig(cluster_manager.cloud_config.cluster.name)

                while not stop_event.is_set():
                    for crd in crds:
                        try:
                            remove_crd_finalizers(crd)
                        except Exception as e:
                            pass
                    time.sleep(1)  # Wait for a second before the next iteration
            except:
                pass

        thread = threading.Thread(target=remove_finalizers_forever)
        thread.start()

        try:
            cluster_manager.destroy()
        finally:
            stop_event.set()
            thread.join()


@cluster_app.command()
def preview(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file. The cluster config file is a "
        "YAML file that contains the configuration of the cluster",
    ),
    policy_packs: List[str] = typer.Option(
        [],
        "--policy-pack",
        "-p",
        help="Path to the policy pack.",
    ),
) -> None:
    """
    Previews the changes that will be applied to the cloud resources.
    """
    cluster_manager = load_cluster_manager(cluster_config)
    if policy_packs:
        cluster_manager.preview(policy_packs=policy_packs)
    else:
        cluster_manager.preview()


@cluster_app.command()
def refresh(
    cluster_config: str = typer.Option(
        "",
        "--file",
        "-f",
        help="Path to the cluster config file. The cluster config file is a "
        "YAML file that contains the configuration of the cluster",
    ),
) -> None:
    """
    Synchronize the local cluster state with the state in the cloud.
    """
    cluster_manager = load_cluster_manager(cluster_config)
    cluster_manager.refresh()

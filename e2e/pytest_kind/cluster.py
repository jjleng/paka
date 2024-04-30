# Code modified from the original repo: https://codeberg.org/hjacobs/pytest-kind/src/branch/main/pytest_kind
from __future__ import annotations

import logging
import os
import platform
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Generator, Optional, Union

import requests
from kubernetes import config

from paka.cluster.kubectl import KUBECTL_VERSION, ensure_kubectl_by_path
from paka.k8s.utils import setup_port_forward
from paka.utils import get_gh_release_latest_version

KIND_VERSION = os.environ.get(
    "KIND_VERSION", get_gh_release_latest_version("kubernetes-sigs/kind")
)


class KindCluster:
    def __init__(
        self,
        name: str,
        kubeconfig: Optional[Path] = None,
        image: Optional[str] = None,
        kind_path: Optional[Path] = None,
        kubectl_path: Optional[Path] = None,
    ):
        self.name = name
        self.image = image
        dir_path = os.path.dirname(os.path.realpath(__file__))

        # Directory for storing states and files
        path = Path(f"{dir_path}/.pytest-kind")

        self.path = path / name
        self.path.mkdir(parents=True, exist_ok=True)
        self.kubeconfig_path = kubeconfig or (self.path / "kubeconfig")

        self.kind_path = kind_path or (self.path / f"kind-{KIND_VERSION}")

        self.system = platform.system().lower()
        self.arch = platform.machine().lower()
        if self.arch in ["amd64", "x86_64"]:
            self.arch = "amd64"

        if self.arch not in ["amd64", "arm64"]:
            raise Exception(f"Unsupported architecture: {self.arch}")

        if self.system == "windows":
            self.kubectl_path = kubectl_path or (
                self.path / f"kubectl-{KUBECTL_VERSION}" / "kubectl.exe"
            )
        else:
            self.kubectl_path = kubectl_path or (
                self.path / f"kubectl-{KUBECTL_VERSION}" / "kubectl"
            )

    def ensure_kind(self) -> None:
        if not self.kind_path.exists():

            url = f"https://github.com/kubernetes-sigs/kind/releases/download/{KIND_VERSION}/kind-{self.system}-{self.arch}"
            logging.info(f"Downloading {url}..")

            tmp_file = self.kind_path.with_suffix(".tmp")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with tmp_file.open("wb") as fd:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            fd.write(chunk)
            tmp_file.chmod(0o755)
            tmp_file.rename(self.kind_path)

    def ensure_kubectl(self) -> None:
        print(self.kubectl_path)
        ensure_kubectl_by_path(self.kubectl_path)

    def create(self, config_file: Optional[Union[str, Path]] = None) -> None:
        """Create the kind cluster if it does not exist (otherwise re-use)."""
        self.ensure_kind()

        self.kubeconfig_path.touch(0o600, exist_ok=True)

        cluster_exists = False

        while not cluster_exists:
            out = subprocess.check_output(
                [str(self.kind_path), "get", "clusters"], encoding="utf-8"
            )
            for name in out.splitlines():
                if name == self.name:
                    cluster_exists = True

            if not cluster_exists:
                create_cmd = [
                    str(self.kind_path),
                    "create",
                    "cluster",
                    f"--name={self.name}",
                    f"--kubeconfig={self.kubeconfig_path}",
                ]

                if self.image:
                    create_cmd += [
                        f"--image={self.image}",  # The docker image for creating the cluster nodes.
                    ]

                if config_file:
                    create_cmd += [f"--config={str(config_file)}"]

                logging.info(f"Creating cluster {self.name}..")
                subprocess.run(create_cmd, check=True)
                cluster_exists = True

            if not self.kubeconfig_path.exists():
                self.delete()
                cluster_exists = False

        config.load_kube_config(config_file=str(self.kubeconfig_path))
        # Set the KUBECONFIG environment variable to the kubeconfig path
        os.environ["KUBECONFIG"] = str(self.kubeconfig_path)

    def load_docker_image(self, docker_image: str) -> None:
        logging.info(f"Loading Docker image {docker_image} in cluster (usually ~5s)..")
        subprocess.run(
            [
                str(self.kind_path),
                "load",
                "docker-image",
                "--name",
                self.name,
                docker_image,
            ],
            check=True,
        )

    def kubectl(self, *args: str, **kwargs: Any) -> str:
        """Run a kubectl command against the cluster and return the output as string."""
        self.ensure_kubectl()
        return subprocess.check_output(
            [str(self.kubectl_path), *args],
            env={**os.environ, "KUBECONFIG": str(self.kubeconfig_path)},
            encoding="utf-8",
            **kwargs,
        )

    @contextmanager
    def port_forward(
        self,
        label_selector: str,
        namespace: str,
        container_port: int,
        local_port: Optional[int] = None,
    ) -> Generator[int, None, None]:
        stop_forward: Optional[Callable[[], None]] = None
        try:
            port, stop = setup_port_forward(
                label_selector, namespace, container_port, local_port
            )
            stop_forward = stop
            yield int(port)
        finally:
            if stop_forward is not None:
                stop_forward()

    def delete(self) -> None:
        """Delete the kind cluster ("kind delete cluster")."""
        logging.info(f"Deleting cluster {self.name}..")
        subprocess.run(
            [
                str(self.kind_path),
                "delete",
                "cluster",
                f"--name={self.name}",
                f"--kubeconfig={self.kubeconfig_path}",
            ],
            check=True,
        )

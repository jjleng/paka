import os
import platform
import shutil
from pathlib import Path

import requests

from paka.logger import logger
from paka.utils import download_url, get_project_data_dir

KUBECTL_VERSION_URL = "https://cdn.dl.k8s.io/release/stable.txt"
CHUNK_SIZE = 8192


def get_latest_kubectl_version() -> str:
    """Return the latest version of kubectl available for download."""
    try:
        response = requests.get(KUBECTL_VERSION_URL)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Failed to get latest kubectl version: {e}")
        return "v1.30.0"


# We are not pinning the version of kubectl to a specific version
# Get the latest version of kubectl should be safe
KUBECTL_VERSION = os.getenv("KUBECTL_VERSION", get_latest_kubectl_version())


# install_path is a full path to the kubectl binary
# It should be in a format like this /path/to/kubectl-x.xx.x/kubectl
def ensure_kubectl_by_path(install_path: Path) -> None:
    """Ensure kubectl is installed at the given path."""
    parent_dir = install_path.parent
    os.environ["PATH"] = f"{parent_dir.absolute()}{os.pathsep}{os.environ['PATH']}"

    if install_path.exists():
        return

    system = platform.system().lower()
    arch = platform.machine().lower()

    if arch in ["amd64", "x86_64"]:
        arch = "amd64"

    if arch not in ["amd64", "arm64"]:
        raise Exception(f"Unsupported architecture: {arch}")

    grandparent_dir = parent_dir.parent

    for old_kubectl_dir in grandparent_dir.glob("kubectl-*"):
        shutil.rmtree(old_kubectl_dir)

    if not install_path.exists():
        url = os.getenv(
            "KUBECTL_DOWNLOAD_URL",
            f"https://dl.k8s.io/release/{KUBECTL_VERSION}/bin/{system}/{arch}/kubectl",
        )
        if system == "windows" and not url.endswith(".exe"):
            url += ".exe"
        logger.info(f"Downloading {url}..")

        with download_url(url) as tmp_file:
            tmp_file_p = Path(tmp_file)
            tmp_file_p.chmod(0o755)
            parent_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tmp_file_p, install_path)


def ensure_kubectl() -> None:
    system = platform.system().lower()
    kubectl_path = (
        Path(get_project_data_dir()) / "bin" / f"kubectl-{KUBECTL_VERSION}" / "kubectl"
    )
    if system == "windows":
        kubectl_path = kubectl_path.with_suffix(".exe")

    ensure_kubectl_by_path(kubectl_path)

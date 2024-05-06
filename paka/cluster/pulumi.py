import os
import platform
import shutil
import tarfile
import zipfile
from pathlib import Path

import requests

from paka.cluster.kubectl import ensure_kubectl
from paka.logger import logger
from paka.utils import calculate_sha256, download_url, get_project_data_dir

# Pin the Pulumi version to avoid breaking changes
PULUMI_VERSION = "v3.114.0"


def change_permissions_recursive(path: Path, mode: int) -> None:
    for child in path.iterdir():
        if child.is_file():
            child.chmod(mode)
        elif child.is_dir():
            child.chmod(mode)
            change_permissions_recursive(child, mode)


def ensure_pulumi() -> None:
    # Plulumi kubernetes provider requires kubectl to be installed
    ensure_kubectl()
    paka_home = Path(get_project_data_dir())

    bin_dir = paka_home / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    system = platform.system().lower()
    arch = platform.machine().lower()

    current_path = os.environ.get("PATH", "")

    pulumi_files = list(bin_dir.glob("pulumi-*"))
    if pulumi_files:
        os.environ["PATH"] = f"{pulumi_files[0]}{os.pathsep}{current_path}"
        return

    pulumi_version = PULUMI_VERSION

    new_pulumi_path = bin_dir / f"pulumi-{pulumi_version}"

    if arch in ["amd64", "x86_64"]:
        arch = "x64"
    elif arch == "arm64":
        arch = "arm64"
    else:
        raise Exception(f"Unsupported architecture: {arch}")

    pulumi_file = f"pulumi-{pulumi_version}-{system}-{arch}"

    if system == "windows":
        pulumi_file = f"{pulumi_file}.zip"
    else:
        pulumi_file = f"{pulumi_file}.tar.gz"

    # First of all, download the checksum file
    checksum_url = f"https://github.com/pulumi/pulumi/releases/download/{pulumi_version}/pulumi-{pulumi_version[1:]}-checksums.txt"

    response = requests.get(checksum_url)
    response.raise_for_status()
    file_sha256_dict = {}
    # Iterate over the lines in the checksum file and split by sha256 and filename
    for line in response.text.strip().split("\n"):
        expected_sha256, filename = line.strip().split()
        file_sha256_dict[filename] = expected_sha256

    url = f"https://github.com/pulumi/pulumi/releases/download/{pulumi_version}/{pulumi_file}"

    logger.info(f"Downloading {pulumi_file}...")

    with download_url(url) as archive_file:
        archive_file_sha256 = calculate_sha256(archive_file)

        if pulumi_file not in file_sha256_dict:
            raise Exception(f"SHA256 not found for {pulumi_file}")

        expected_sha256 = file_sha256_dict[pulumi_file]

        if archive_file_sha256 != expected_sha256:
            raise Exception(
                f"SHA256 mismatch: {archive_file_sha256} != {expected_sha256}"
            )

        if system == "windows":
            with zipfile.ZipFile(archive_file, "r") as zip_ref:
                zip_ref.extractall(bin_dir)
        else:
            with tarfile.open(archive_file, "r:gz") as tar:
                tar.extractall(bin_dir)

    pulumi_path = bin_dir / "pulumi"
    change_permissions_recursive(pulumi_path, 0o755)
    pulumi_path = pulumi_path.rename(new_pulumi_path)

    # For windows, the Pulumi binary is under pulumi_path/bin
    # For other platforms, the Pulumi binary is under pulumi_path
    if system == "windows":
        windows_bin_path = pulumi_path / "bin"
        for file in windows_bin_path.iterdir():
            if file.is_file():
                shutil.move(str(file), str(pulumi_path))

    logger.info("Pulumi installed successfully.")

    os.environ["PATH"] = f"{pulumi_path}{os.pathsep}{current_path}"

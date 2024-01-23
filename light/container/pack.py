import os
import platform
import shutil
import tarfile
import tempfile
import zipfile

import requests

from light.logger import logger


def get_latest_pack_version() -> str:
    url = "https://api.github.com/repos/buildpacks/pack/releases/latest"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return data["tag_name"][1:]  # Remove the 'v' prefix


def install_pack() -> None:
    if shutil.which("pack"):
        return

    system = platform.system().lower()
    arch = platform.machine().lower()

    if system == "darwin":
        system = "macos"

    pack_version = get_latest_pack_version()

    if system == "windows":
        pack_file = f"pack-v{pack_version}-windows.zip"

        program_files_dir = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        bin_dir = os.path.join(
            program_files_dir, "pack"
        )  # Replace 'YourAppName' with your application's name

        # Check if the script is running with administrator privileges
        if not os.path.exists(bin_dir):
            try:
                os.makedirs(bin_dir)
            except PermissionError:
                logger.error("Administrator privileges required.")
                raise

    elif arch in ["amd64", "x86_64"]:
        pack_file = f"pack-v{pack_version}-{system}.tgz"
    elif arch == "arm64":
        pack_file = f"pack-v{pack_version}-{system}-{arch}.tgz"
    else:
        raise Exception(f"Unsupported architecture: {arch}")

    url = f"https://github.com/buildpacks/pack/releases/download/v{pack_version}/{pack_file}"

    logger.info(f"Downloading {pack_file}...")
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    tf.write(chunk)
            local_file = tf.name

        if system == "windows":
            with zipfile.ZipFile(local_file, "r") as zip_ref:
                zip_ref.extractall(bin_dir)
        else:
            with tarfile.open(local_file, "r:gz") as tar:
                tar.extractall("/usr/local/bin")
            os.chmod("/usr/local/bin/pack", 0o755)
    finally:
        if local_file is not None:
            os.unlink(local_file)

    logger.info("Pack installed successfully.")

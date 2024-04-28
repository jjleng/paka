import hashlib
import os
import platform
import tarfile
import tempfile
import zipfile
from pathlib import Path

import requests

from paka.logger import logger
from paka.utils import get_project_data_dir


def get_latest_pack_version() -> str:
    url = "https://api.github.com/repos/buildpacks/pack/releases/latest"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return data["tag_name"]


def calculate_sha256(file_path: str) -> str:
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def ensure_pack() -> str:
    paka_home = Path(get_project_data_dir())

    bin_dir = paka_home / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    pack_files = list(bin_dir.glob("pack-*"))
    if pack_files:
        return str(pack_files[0])

    pack_version = get_latest_pack_version()

    new_pack_path = bin_dir / f"pack-{pack_version}"

    system = platform.system().lower()
    arch = platform.machine().lower()

    if system == "windows":
        new_pack_path = new_pack_path.with_suffix(".exe")

    if new_pack_path.exists():
        return str(new_pack_path)

    for old_pack_path in bin_dir.glob("pack-*"):
        if old_pack_path.is_file():
            old_pack_path.unlink()

    if system == "darwin":
        system = "macos"

    if system == "windows":
        pack_file = f"pack-{pack_version}-windows.zip"

    elif arch in ["amd64", "x86_64"]:
        pack_file = f"pack-{pack_version}-{system}.tgz"
    elif arch == "arm64":
        pack_file = f"pack-{pack_version}-{system}-{arch}.tgz"
    else:
        raise Exception(f"Unsupported architecture: {arch}")

    url = f"https://github.com/buildpacks/pack/releases/download/{pack_version}/{pack_file}"

    logger.info(f"Downloading {pack_file}...")

    with tempfile.NamedTemporaryFile() as tf:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=8192):
                tf.write(chunk)

        tf.flush()
        os.fsync(tf.fileno())

        archive_file = tf.name

        archive_file_sha256 = calculate_sha256(archive_file)

        # Now, fetch the sha256 file and compare the hash
        sha256_url = f"{url}.sha256"

        response = requests.get(sha256_url)
        response.raise_for_status()
        expected_sha256, expected_filename = response.text.strip().split()

        assert expected_filename == pack_file

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
        pack_path = bin_dir / "pack"

        if system == "windows":
            pack_path = pack_path.with_suffix(".exe")

        pack_path.chmod(0o755)
        pack_path.rename(new_pack_path)

    logger.info("Pack installed successfully.")

    return str(new_pack_path)

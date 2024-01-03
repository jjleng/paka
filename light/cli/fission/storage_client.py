from typing import Tuple, Callable, Optional, Type
from types import TracebackType
import os
import requests
import hashlib
from urllib.parse import quote
from collections import namedtuple
from urllib.parse import urljoin
from light.k8s import setup_port_forward

STORAGE_CONTAINER_PORT = 8000
FISSION_STORAGESVC_URL = "http://storagesvc.fission/v1"

Checksum = namedtuple("Checksum", ["type", "sum"])


class StorageClient:
    def __init__(self, kubeconfig_name: str, namespace: str):
        self.kubeconfig_name = kubeconfig_name
        self.namespace = namespace
        (
            self.storage_url,
            self.stop_forward,
        ) = self.get_storage_url()

    def __enter__(self) -> "StorageClient":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.stop_forward()

    def get_storage_url(
        self,
    ) -> Tuple[str, Callable[[], None]]:
        local_port, stop_forward = setup_port_forward(
            self.kubeconfig_name,
            "application=fission-storage",
            self.namespace,
            STORAGE_CONTAINER_PORT,
        )

        server_url = f"http://localhost:{local_port}/v1"

        return server_url, stop_forward

    def upload_file(self, file_path: str) -> str:
        try:
            file_size = os.path.getsize(file_path)
            headers = {"X-File-Size": str(file_size)}
            with open(file_path, "rb") as f:
                files = {"uploadfile": (os.path.basename(file_path), f)}
                response = requests.post(
                    self.storage_url + "/archive", files=files, headers=headers
                )
                response.raise_for_status()
                id = response.json()["id"]
                return id
        except Exception as e:
            print(f"Error uploading file: {str(e)}")
            raise

    def get_archive_url(self, archive_id: str) -> str:
        try:
            storage_access_url = f"{self.storage_url}/archive?id={quote(archive_id)}"

            response = requests.head(storage_access_url)
            response.raise_for_status()

            storage_type = response.headers.get("X-FISSION-STORAGETYPE")

            if storage_type == "local":
                return f"{FISSION_STORAGESVC_URL}/archive?id={quote(archive_id)}"
            elif storage_type == "s3":
                raise NotImplementedError("S3 storage type not implemented")
            else:
                raise Exception(f"Unknown storage type: {storage_type}")
        except Exception as e:
            print(f"Error getting archive URL: {str(e)}")
            raise

    @staticmethod
    def get_file_checksum(file_name: str) -> Checksum:
        try:
            with open(file_name, "rb") as f:
                sha256_hash = hashlib.sha256()
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
                return Checksum("sha256", sha256_hash.hexdigest())
        except Exception as e:
            print(f"Failed to open file {file_name} or calculate checksum: {str(e)}")
            raise

    def upload_archive_file(self, file_name: str) -> str:
        try:
            archive_id = self.upload_file(file_name)
            return self.get_archive_url(archive_id)
        except Exception as e:
            print(f"Error uploading archive file: {str(e)}")
            raise

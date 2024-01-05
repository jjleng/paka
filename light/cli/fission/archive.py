from collections import namedtuple
from typing import List

from light.cli.fission.storage import StorageClient

FISSION_RELEASE_NS = "fission"
ARCHIVE_TYPE_URL = "url"
ARCHIVE_TYPE_LITERAL = "literal"

Archive = namedtuple("Archive", ["type", "literal", "url", "checksum"])


def create_archive(archive_file: str) -> Archive:
    with StorageClient(FISSION_RELEASE_NS) as storage_client:
        archive_url = storage_client.upload_archive_file(archive_file)
        checksum = storage_client.get_file_checksum(archive_file)
        return Archive(ARCHIVE_TYPE_URL, "", archive_url, checksum)


def list_archive_files() -> List[str]:
    with StorageClient(FISSION_RELEASE_NS) as storage_client:
        return storage_client.list_archive_files()


def delete_archive(archive_id: str) -> None:
    with StorageClient(FISSION_RELEASE_NS) as storage_client:
        storage_client.delete_archive_file(archive_id)

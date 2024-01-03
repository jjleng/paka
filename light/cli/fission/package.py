import uuid
import datetime
from typing import Dict, Any
from kubernetes import client
from light.cli.fission.storage import StorageClient
from light.cli.fission.archive import Archive, ARCHIVE_TYPE_URL
from light.k8s import CustomResource, apply_resource

FISSION_RELEASE_NS = "fission"


def create_archive(kubeconfig_name: str, archive_file: str) -> Archive:
    with StorageClient(kubeconfig_name, FISSION_RELEASE_NS) as storage_client:
        archive_url = storage_client.upload_archive_file(archive_file)
        checksum = storage_client.get_file_checksum(archive_file)
        return Archive(ARCHIVE_TYPE_URL, "", archive_url, checksum)


def create_package(
    kubeconfig_name: str,
    pkg_name: str,
    pkg_namespace: str,
    env_name: str,
    src_archive_file: str,
    buildcmd: str,
) -> dict:
    pkg_spec: Dict[str, Any] = {
        "environment": {
            "namespace": pkg_namespace,
            "name": env_name,
        },
    }

    pkg_status = "succeeded"

    if len(src_archive_file) > 0:
        archive = create_archive(kubeconfig_name, src_archive_file)
        archive_dict = archive._asdict()
        archive_dict["checksum"] = archive.checksum._asdict()
        pkg_spec["source"] = archive_dict
        pkg_status = "pending"

    if len(buildcmd) > 0:
        pkg_spec["buildcmd"] = buildcmd

    if len(pkg_name) == 0:
        pkg_name = str(uuid.uuid4()).lower()

    try:
        package_crd = CustomResource(
            api_version="fission.io/v1",
            kind="Package",
            plural="packages",
            metadata=client.V1ObjectMeta(name=pkg_name, namespace=pkg_namespace),
            spec=pkg_spec,
            status={
                "buildstatus": pkg_status,
                "lastUpdateTimestamp": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
            },
        )
        apply_resource(kubeconfig_name, package_crd)
        print(f"Package '{package_crd.metadata.name}' created")
        return package_crd.metadata.to_dict()
    except Exception as e:
        print(f"Error creating package: {str(e)}")
        raise

import datetime
import uuid
from typing import Any, Dict

from kubernetes import client

from light.cli.fission.archive import create_archive
from light.k8s import (
    CustomResource,
    apply_resource,
    delete_namespaced_custom_object,
    list_namespaced_custom_object,
    read_namespaced_custom_object,
)


def upsert_package(
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
        # We create a new archive and update the package spec
        # Old archive will be garbage collected
        archive = create_archive(src_archive_file)
        archive_dict = archive._asdict()
        archive_dict["checksum"] = archive.checksum._asdict()
        pkg_spec["source"] = archive_dict
        pkg_status = "pending"

    if len(buildcmd) > 0:
        pkg_spec["buildcmd"] = buildcmd

    if len(pkg_name) == 0:
        pkg_name = str(uuid.uuid4()).lower()

    package_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Package",
        plural="packages",
        metadata=client.V1ObjectMeta(name=pkg_name, namespace=pkg_namespace),
        spec=pkg_spec,
        status={
            "buildstatus": pkg_status,
            # triggers a new build
            "lastUpdateTimestamp": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat(),
        },
    )
    # Update the resource if it already exists
    apply_resource(package_crd)
    return package_crd.metadata.to_dict()


def get_package(
    pkg_name: str,
    pkg_namespace: str,
) -> dict:
    package_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Package",
        plural="packages",
        metadata=client.V1ObjectMeta(name=pkg_name, namespace=pkg_namespace),
        spec={},
    )

    package = read_namespaced_custom_object(pkg_name, pkg_namespace, package_crd)

    return package


def delete_package(
    pkg_name: str,
    pkg_namespace: str,
) -> None:
    package_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Package",
        plural="packages",
        metadata=client.V1ObjectMeta(name=pkg_name, namespace=pkg_namespace),
        spec={},
    )

    delete_namespaced_custom_object(pkg_name, pkg_namespace, package_crd)


def list_packages(
    pkg_namespace: str,
) -> dict:
    package_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Package",
        plural="packages",
        metadata=client.V1ObjectMeta(namespace=pkg_namespace),
        spec={},
    )

    packages = list_namespaced_custom_object(pkg_namespace, package_crd)

    return packages

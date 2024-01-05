import json

from light.fission.package import get_package
from light.job.entrypoint import write_entrypoint_script_to_cfgmap
from light.k8s import create_namespace


def test_write_entrypoint(namespace: str, package_name: str) -> None:
    package = get_package(
        package_name,
        namespace,
    )

    fetch_payload = {
        "FetchType": 1,
        "FileName": package_name,
        "Package": {
            "Name": package_name,
            "Namespace": namespace,
            "ResourceVersion": package["metadata"]["resourceVersion"],
        },
        "KeepArchive": False,
    }

    create_namespace("celery-workers")
    write_entrypoint_script_to_cfgmap(
        "jobs", "celery -A celery.main worker", json.dumps(fetch_payload)
    )

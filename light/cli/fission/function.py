from kubernetes import client
from light.k8s import (
    CustomResource,
    apply_resource,
    load_kubeconfig,
    read_namespaced_custom_object,
    delete_namespaced_custom_object,
    list_namespaced_custom_object,
)
from light.cli.fission.package import get_package

ExecutorTypePoolmgr = "poolmgr"
ExecutorTypeNewdeploy = "newdeploy"
ExecutorTypeContainer = "container"


def upsert_fn(
    kubeconfig_name: str,
    fn_name: str,
    fn_namespace: str,
    pkg_name: str,
    entrypoint: str,
    concurrency: int = 500,
    timeout: int = 60,
    idle_timeout: int = 120,
    requests_per_pod: int = 1,
) -> dict:
    # read the package
    pkg = get_package(kubeconfig_name, pkg_name, fn_namespace)
    fn_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Function",
        plural="functions",
        metadata=client.V1ObjectMeta(name=fn_name, namespace=fn_namespace),
        spec={
            "version": 2,
            "InvokeStrategy": {
                "ExecutionStrategy": {
                    "ExecutorType": ExecutorTypePoolmgr,
                    # "poolmgr" doesn't support minscale/maxscale and targetcpu
                    "MaxScale": 0,
                    "MinScale": 0,
                    "TargetCPUPercent": 0,
                    "SpecializationTimeout": 120,
                },
                "StrategyType": "execution",
            },
            "concurrency": concurrency,
            "environment": pkg["spec"]["environment"],
            "functionTimeout": timeout,
            "idletimeout": idle_timeout,
            "package": {
                "functionName": entrypoint,
                "packageref": {
                    "name": pkg["metadata"]["name"],
                    "namespace": pkg["metadata"]["namespace"],
                    "resourceversion": pkg["metadata"]["resourceVersion"],
                },
            },
            "requestsPerPod": requests_per_pod,
            "resources": {},
        },
    )
    apply_resource(kubeconfig_name, fn_crd)

    return fn_crd.metadata.to_dict()


def get_fn(
    kubeconfig_name: str,
    fn_name: str,
    fn_namespace: str,
) -> dict:
    load_kubeconfig(kubeconfig_name)
    fn_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Function",
        plural="functions",
        metadata=client.V1ObjectMeta(name=fn_name, namespace=fn_namespace),
        spec={},
    )

    fn = read_namespaced_custom_object(fn_name, fn_namespace, fn_crd)

    return fn


def delete_fn(
    kubeconfig_name: str,
    fn_name: str,
    fn_namespace: str,
) -> None:
    load_kubeconfig(kubeconfig_name)
    fn_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Function",
        plural="functions",
        metadata=client.V1ObjectMeta(name=fn_name, namespace=fn_namespace),
        spec={},
    )

    delete_namespaced_custom_object(fn_name, fn_namespace, fn_crd)


def list_fns(
    kubeconfig_name: str,
    fn_namespace: str,
) -> dict:
    load_kubeconfig(kubeconfig_name)
    fn_crd = CustomResource(
        api_version="fission.io/v1",
        kind="Function",
        plural="functions",
        metadata=client.V1ObjectMeta(namespace=fn_namespace),
        spec={},
    )

    fns = list_namespaced_custom_object(fn_namespace, fn_crd)

    return fns

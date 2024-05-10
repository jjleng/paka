from kubernetes.client import V1PodTemplateSpec

from paka.cluster.context import Context
from paka.config import (
    AwsConfig,
    AwsGpuNodeConfig,
    AwsModelGroup,
    ClusterConfig,
    Config,
    ResourceRequest,
    Runtime,
)
from paka.constants import MODEL_MOUNT_PATH
from paka.k8s.model_group.service import create_pod


def test_create_pod() -> None:
    model_group = AwsModelGroup(
        nodeType="c7a.xlarge",
        minInstances=1,
        maxInstances=1,
        name="llama2-7b",
        resourceRequest=ResourceRequest(cpu="100m", memory="256Mi", gpu=2),
        gpu=AwsGpuNodeConfig(diskSize=100, enabled=True),
        runtime=Runtime(
            image="johndoe/llama.cpp:server",
            command=["/server", "--model", f"{MODEL_MOUNT_PATH}/model.ggml"],
        ),
    )

    config = Config(
        version="1.0",
        aws=AwsConfig(
            cluster=ClusterConfig(
                name="test_cluster",
                region="us-west-2",
                nodeType="t2.medium",
                minNodes=2,
                maxNodes=4,
            ),
            modelGroups=[model_group],
        ),
    )

    ctx = Context()
    ctx.set_config(config)

    pod = create_pod(ctx, "test_namespace", model_group, 8080)

    assert isinstance(pod, V1PodTemplateSpec)
    assert pod.metadata and pod.spec

    assert pod.metadata.name == "llama2-7b"
    assert pod.metadata.namespace == "test_namespace"
    assert len(pod.spec.containers) == 1
    container = pod.spec.containers[0]

    assert container and container.resources

    assert container.name == "llama2-7b"
    assert container.image == "johndoe/llama.cpp:server"
    assert container.resources.requests
    assert container.resources.requests["cpu"] == "100m"
    assert container.resources.requests["memory"] == "256Mi"
    assert container.resources.limits
    assert container.resources.limits["nvidia.com/gpu"] == "2"
    assert container.volume_mounts
    assert len(container.volume_mounts) == 1
    assert container.volume_mounts[0].name == "model-data"
    assert container.volume_mounts[0].mount_path == MODEL_MOUNT_PATH

    assert container.env
    assert len(container.env) == 1
    assert container.env[0].name == "PORT"
    assert container.env[0].value == "8080"

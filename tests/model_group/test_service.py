from kubernetes.client import V1Pod

from paka.config import (
    AwsGpuNode,
    CloudConfig,
    CloudModelGroup,
    ClusterConfig,
    Config,
    ResourceRequest,
)
from paka.kube_resources.model_group.service import create_pod


def test_create_pod() -> None:
    model_group = CloudModelGroup(
        nodeType="c7a.xlarge",
        minInstances=1,
        maxInstances=1,
        name="llama2-7b",
        resourceRequest=ResourceRequest(cpu="100m", memory="256Mi", gpu=2),
        awsGpu=AwsGpuNode(diskSize=100),
    )

    config = Config(
        aws=CloudConfig(
            cluster=ClusterConfig(
                name="test_cluster",
                region="us-west-2",
                nodeType="t2.medium",
                minNodes=2,
                maxNodes=4,
            ),
            modelGroups=[model_group],
        )
    )

    pod = create_pod("test_namespace", config, model_group, "runtime_image", 8080)

    assert isinstance(pod, V1Pod)

    assert pod.metadata.name == "llama2-7b"
    assert pod.metadata.namespace == "test_namespace"
    assert len(pod.spec.containers) == 1
    container = pod.spec.containers[0]
    assert container.name == "llama2-7b"
    assert container.image == "runtime_image"
    assert container.resources.requests["cpu"] == "100m"
    assert container.resources.requests["memory"] == "256Mi"
    assert container.resources.limits["nvidia.com/gpu"] == 2
    assert len(container.volume_mounts) == 1
    assert container.volume_mounts[0].name == "model-data"
    assert container.volume_mounts[0].mount_path == "/data"
    assert len(container.env) == 3
    assert container.env[0].name == "N_GPU_LAYERS"
    assert container.env[0].value == "-1"  # Offload all layers to GPU
    assert container.env[1].name == "MODEL"
    assert container.env[1].value == "/data/my_model.gguf"
    assert container.env[2].name == "PORT"
    assert container.env[2].value == "8080"

    model_group = CloudModelGroup(
        nodeType="c7a.xlarge",
        minInstances=1,
        maxInstances=1,
        name="llama2-7b",
    )

    config = Config(
        aws=CloudConfig(
            cluster=ClusterConfig(
                name="test_cluster",
                region="us-west-2",
                nodeType="t2.medium",
                minNodes=2,
                maxNodes=4,
            ),
            modelGroups=[model_group],
        )
    )

    pod = create_pod("test_namespace", config, model_group, "runtime_image", 8080)

    assert isinstance(pod, V1Pod)

    assert len(pod.spec.containers) == 1
    container = pod.spec.containers[0]
    assert container.name == "llama2-7b"
    assert container.image == "runtime_image"
    assert len(container.volume_mounts) == 1
    assert container.volume_mounts[0].name == "model-data"
    assert container.volume_mounts[0].mount_path == "/data"
    assert len(container.env) == 3
    assert container.env[0].name == "N_GPU_LAYERS"
    assert container.env[0].value == "0"  # Offload no layers to GPU
    assert container.env[1].name == "MODEL"
    assert container.env[1].value == "/data/my_model.gguf"
    assert container.env[2].name == "PORT"
    assert container.env[2].value == "8080"

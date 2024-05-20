from kubernetes.client import V1PodTemplateSpec, V1Probe

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
from paka.k8s.model_group.service import (
    create_env_vars,
    create_pod,
    create_probe,
    create_volume_mounts,
)


def test_create_env_vars() -> None:
    env = [{"name": "TEST_ENV", "value": "test_value"}]
    port = 8080
    env_vars = create_env_vars(env, port)
    assert len(env_vars) == 2
    assert env_vars[0].name == "TEST_ENV"
    assert env_vars[0].value == "test_value"
    assert env_vars[1].name == "PORT"
    assert env_vars[1].value == str(port)


def test_create_volume_mounts() -> None:
    volume_mounts = [{"name": "test-volume", "mountPath": "/test/path"}]
    mounts = create_volume_mounts(volume_mounts)
    assert len(mounts) == 2
    assert mounts[0].name == "model-data"
    assert mounts[1].name == "test-volume"
    assert mounts[1].mount_path == "/test/path"


def test_create_probe() -> None:
    probe_dict = {
        "httpGet": {"path": "/test/path", "port": 8080},
        "initialDelaySeconds": 5,
        "periodSeconds": 5,
        "timeoutSeconds": 30,
        "successThreshold": 1,
        "failureThreshold": 5,
    }
    probe = create_probe(probe_dict, "/default/path", 8000, 10)
    assert isinstance(probe, V1Probe)
    assert probe.http_get
    assert probe.http_get.path == "/test/path"
    assert probe.http_get.port == 8080
    assert probe.initial_delay_seconds == 5
    assert probe.period_seconds == 5
    assert probe.timeout_seconds == 30
    assert probe.success_threshold == 1
    assert probe.failure_threshold == 5


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
            env=[{"name": "TEST_ENV", "value": "test_value"}],
            volumeMounts=[{"name": "test-volume", "mountPath": "/test/path"}],
            readinessProbe={
                "httpGet": {"path": "/ready", "port": 8080},
                "initialDelaySeconds": 5,
                "periodSeconds": 5,
            },
            livenessProbe={
                "httpGet": {"path": "/live", "port": 8080},
                "initialDelaySeconds": 5,
                "periodSeconds": 5,
            },
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
    assert len(container.volume_mounts) == 2
    assert container.volume_mounts[0].name == "model-data"
    assert container.volume_mounts[0].mount_path == MODEL_MOUNT_PATH
    assert container.volume_mounts[1].name == "test-volume"
    assert container.volume_mounts[1].mount_path == "/test/path"

    assert container.env
    assert len(container.env) == 2
    assert container.env[0].name == "TEST_ENV"
    assert container.env[0].value == "test_value"
    assert container.env[1].name == "PORT"
    assert container.env[1].value == "8080"

    assert container.readiness_probe and container.readiness_probe.http_get
    assert container.readiness_probe.http_get.path == "/ready"
    assert container.readiness_probe.http_get.port == 8080
    assert container.readiness_probe.initial_delay_seconds == 5
    assert container.readiness_probe.period_seconds == 5

    assert container.liveness_probe and container.liveness_probe.http_get
    assert container.liveness_probe.http_get.path == "/live"
    assert container.liveness_probe.http_get.port == 8080
    assert container.liveness_probe.initial_delay_seconds == 5
    assert container.liveness_probe.period_seconds == 5

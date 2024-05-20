from unittest.mock import MagicMock, patch

import paka.k8s.model_group.runtime.vllm
from paka.cluster.context import Context
from paka.config import AwsModelGroup, Model, Runtime
from paka.k8s.model_group.runtime.vllm import get_runtime_command_vllm, is_vllm_image


def test_is_vllm_image() -> None:
    assert is_vllm_image("vllm:latest") == True
    assert is_vllm_image("notvllm:latest") == False


def test_get_runtime_command_vllm() -> None:
    mock_store = MagicMock()
    with patch.object(
        paka.k8s.model_group.runtime.vllm,
        "get_model_store",
        return_value=mock_store,
    ) as mock_get_model_store, patch.object(
        paka.k8s.model_group.runtime.vllm,
        "validate_repo_id",
        return_value=True,
    ) as mock_validate_repo_id:
        ctx = Context()
        model_group = AwsModelGroup(
            name="test",
            minInstances=1,
            maxInstances=2,
            nodeType="t2.micro",
            runtime=Runtime(image="vllm:latest", command=["python", "app.py"]),
            model=Model(useModelStore=True),
            resourceRequest={"cpu": "1000", "memory": "1Gi"},
        )

        command = get_runtime_command_vllm(ctx, model_group)
        assert command == ["python", "app.py", "--model", "/data"]

        model_group.runtime.command = None
        command = get_runtime_command_vllm(ctx, model_group)
        assert command == [
            "python3",
            "-O",
            "-u",
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--host",
            "0.0.0.0",
            "--model",
            "/data",
        ]

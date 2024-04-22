from unittest.mock import patch

import pytest

import paka.kube_resources.model_group.runtime.llama_cpp
from paka.config import CloudModelGroup, Model, Runtime
from paka.kube_resources.model_group.runtime.llama_cpp import (
    get_runtime_command_llama_cpp,
)


@pytest.fixture
def model_group() -> CloudModelGroup:
    return CloudModelGroup(
        name="test-model-group",
        minInstances=1,
        maxInstances=2,
        nodeType="t2.micro",
        runtime=Runtime(
            image="johndoe/llama.cpp:server",
            command=["/server", "--model", "/data/model.ggml"],
        ),
    )


def test_get_runtime_command_llama_cpp(model_group: CloudModelGroup) -> None:
    with patch("os.listdir") as mock_listdir, patch.object(
        paka.kube_resources.model_group.runtime.llama_cpp, "HfFileSystem"
    ) as mock_hf_fs, patch.object(
        paka.kube_resources.model_group.runtime.llama_cpp,
        "validate_repo_id",
        return_value=True,
    ) as mock_validate_repo_id:
        # Test case: runtime command is already provided
        assert get_runtime_command_llama_cpp(model_group) == [
            "/server",
            "--model",
            "/data/model.ggml",
        ]

        # Test case: model file is found in /data directory
        model_group.runtime.command = None
        model_group.model = Model(useModelStore=True)
        # Mock os.listdir to return a specific list of files
        mock_listdir.return_value = ["model.ggml"]
        command = get_runtime_command_llama_cpp(model_group)
        assert "--model" in command, "Expected '--model' to be in command list"
        model_index = command.index("--model")
        assert (
            command[model_index + 1] == "/data/model.ggml"
        ), "Expected '--model' to be followed by '/data/model.ggml'"

        # Test case: model file is not found in /data directory but found in HuggingFace repo
        model_group.model = Model(
            useModelStore=True, hfRepoId="repoId", files=["model.ggml"]
        )
        # Mock os.listdir to return an empty list
        mock_listdir.return_value = []
        # Mock HfFileSystem.glob to return a specific list of files
        mock_hf_fs.return_value.glob.return_value = ["model.ggml"]
        command = get_runtime_command_llama_cpp(model_group)
        assert "--hf-repo" in command, "Expected '--hf-repo' to be in command list"
        repo_index = command.index("--hf-repo")
        assert (
            command[repo_index + 1] == "repoId"
        ), "Expected '--hf-repo' to be followed by 'repoId'"

        assert "--hf-file" in command, "Expected '--hf-file' to be in command list"
        file_index = command.index("--hf-file")
        assert (
            command[file_index + 1] == "model.ggml"
        ), "Expected '--hf-file' to be followed by 'model.ggml'"

        # Test case: model file is not found in /data directory and not found in HuggingFace repo
        model_group.model = Model(
            useModelStore=True, hfRepoId="repoId", files=["model.ggml"]
        )
        # Mock os.listdir to return an empty list
        mock_listdir.return_value = []
        # Mock HfFileSystem.glob to return an empty list
        mock_hf_fs.return_value.glob.return_value = []
        with pytest.raises(
            ValueError, match="No model file found in HuggingFace repo."
        ):
            get_runtime_command_llama_cpp(model_group)

        # Test case: Multiple model files found in /data directory
        model_group.model = Model(useModelStore=True)
        # Mock os.listdir to return multiple model files
        mock_listdir.return_value = ["model1.ggml", "model2.ggml"]
        with pytest.raises(
            ValueError, match="Multiple model files found in /data directory."
        ):
            get_runtime_command_llama_cpp(model_group)

        # Test case: No model file found in /data directory
        model_group.model = Model(useModelStore=True)
        # Mock os.listdir to return an empty list
        mock_listdir.return_value = []
        mock_hf_fs.return_value.glob.return_value = []
        with pytest.raises(ValueError, match="Did not find a model to load."):
            get_runtime_command_llama_cpp(model_group)

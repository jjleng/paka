from unittest.mock import MagicMock, patch

import pytest

import paka.k8s.model_group.runtime.llama_cpp
from paka.config import CloudModelGroup, Model, Runtime
from paka.constants import MODEL_MOUNT_PATH
from paka.k8s.model_group.runtime.llama_cpp import get_runtime_command_llama_cpp


@pytest.fixture
def model_group() -> CloudModelGroup:
    return CloudModelGroup(
        name="test-model-group",
        minInstances=1,
        maxInstances=2,
        nodeType="t2.micro",
        runtime=Runtime(
            image="johndoe/llama.cpp:server",
            command=["/server", "--model", f"{MODEL_MOUNT_PATH}/model.gguf"],
        ),
    )


def test_get_runtime_command_llama_cpp(model_group: CloudModelGroup) -> None:
    mock_store = MagicMock()
    with patch.object(
        paka.k8s.model_group.runtime.llama_cpp.BaseMLModel,
        "get_model_store",
        return_value=mock_store,
    ) as mock_get_model_store, patch.object(
        paka.k8s.model_group.runtime.llama_cpp, "HfFileSystem"
    ) as mock_hf_fs, patch.object(
        paka.k8s.model_group.runtime.llama_cpp,
        "validate_repo_id",
        return_value=True,
    ) as mock_validate_repo_id:
        # Test case: runtime command is already provided
        assert get_runtime_command_llama_cpp(model_group) == [
            "/server",
            "--model",
            f"{MODEL_MOUNT_PATH}/model.gguf",
        ]

        # Test case: model file is found in model store
        model_group.runtime.command = None
        model_group.model = Model(useModelStore=True)
        # Mock os.listdir to return a specific list of files
        mock_store.glob.return_value = ["model.gguf"]
        command = get_runtime_command_llama_cpp(model_group)
        assert "--model" in command, "Expected '--model' to be in command list"
        model_index = command.index("--model")
        assert (
            command[model_index + 1] == f"{MODEL_MOUNT_PATH}/model.gguf"
        ), f"Expected '--model' to be followed by '{MODEL_MOUNT_PATH}/model.gguf'"

        # Test case: model file is not found in the model store but found in HuggingFace repo
        model_group.model = Model(
            useModelStore=True, hfRepoId="repoId", files=["model.gguf"]
        )
        # Mock os.listdir to return an empty list
        mock_store.glob.return_value = []
        # Mock HfFileSystem.glob to return a specific list of files
        mock_hf_fs.return_value.glob.return_value = ["model.gguf"]
        command = get_runtime_command_llama_cpp(model_group)
        assert "--hf-repo" in command, "Expected '--hf-repo' to be in command list"
        repo_index = command.index("--hf-repo")
        assert (
            command[repo_index + 1] == "repoId"
        ), "Expected '--hf-repo' to be followed by 'repoId'"

        assert "--hf-file" in command, "Expected '--hf-file' to be in command list"
        file_index = command.index("--hf-file")
        assert (
            command[file_index + 1] == "model.gguf"
        ), "Expected '--hf-file' to be followed by 'model.gguf'"

        # Test case: model file is not found in the model store and not found in HuggingFace repo
        model_group.model = Model(
            useModelStore=True, hfRepoId="repoId", files=["model.gguf"]
        )
        # Mock os.listdir to return an empty list
        mock_store.glob.return_value = []
        # Mock HfFileSystem.glob to return an empty list
        mock_hf_fs.return_value.glob.return_value = []
        with pytest.raises(
            ValueError, match="No model file found in HuggingFace repo."
        ):
            get_runtime_command_llama_cpp(model_group)

        # Test case: Multiple model files found in the model store
        model_group.model = Model(useModelStore=True)
        # Mock os.listdir to return multiple model files
        mock_store.glob.return_value = ["model1.ggml", "model2.ggml"]
        with pytest.raises(
            ValueError,
            match=f"Multiple model files found in {model_group.name}/ directory.",
        ):
            get_runtime_command_llama_cpp(model_group)

        # Test case: No model file found in the model store
        model_group.model = Model(useModelStore=True)
        # Mock os.listdir to return an empty list
        mock_store.glob.return_value = []
        mock_hf_fs.return_value.glob.return_value = []
        with pytest.raises(ValueError, match="Did not find a model to load."):
            get_runtime_command_llama_cpp(model_group)

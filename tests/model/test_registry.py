from unittest.mock import MagicMock, Mock, patch

import pytest

from paka.model.hf_model import BaseMLModel


@patch.object(BaseMLModel, "get_model_store", return_value=MagicMock())
def test_get_model(get_model_store_mock: Mock) -> None:
    from paka.model.registry import HuggingFaceModel, get_model, model_registry

    model_registry.append(
        HuggingFaceModel(
            name="test_model",
            repo_id="test_repo",
            files=[],
            inference_devices=["cpu"],
            quantization="GGUF_Q4_0",
            runtime="llama.cpp",
        )
    )

    # Test that get_model returns the correct model
    model = get_model("test_model", [("quantization", "GGUF_Q4_0")])
    assert model.name == "test_model"
    assert model.repo_id == "test_repo"

    # Test that get_model raises a ValueError when the model is not found
    with pytest.raises(ValueError):
        get_model("nonexistent_model")

    # Test that get_model raises a ValueError when multiple models are found
    model_registry.append(
        HuggingFaceModel(
            name="test_model",
            repo_id="test_repo_2",
            files=[],
            inference_devices=["cpu"],
            quantization="GGUF_Q4_0",
            runtime="llama.cpp",
        )
    )
    with pytest.raises(ValueError):
        get_model("test_model", [("quantization", "GGUF_Q4_0")])

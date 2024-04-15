from unittest.mock import MagicMock, patch

import paka.model.hf_model
from paka.model.hf_model import BaseMLModel, HuggingFaceModel


def test_hf_model() -> None:
    with patch.object(
        paka.model.hf_model, "HfFileSystem", autospec=True
    ) as mock_hf_file_system, patch.object(
        BaseMLModel,
        "get_model_store",
        return_value=MagicMock(),
    ) as mock_get_model_store, patch.object(
        BaseMLModel,
        "finish",
        return_value=MagicMock(),
    ) as finish_mock:
        model = HuggingFaceModel(
            name="TestModel",
            repo_id="test-repo",
            files=["file1", "file2"],
            inference_devices=["cpu", "gpu"],
            quantization="GPTQ",
            runtime="llama.cpp",
        )

        mock_hf_file_system.return_value.glob.return_value = ["file1", "file2"]
        mock_hf_file_system.return_value.stat.return_value = {
            "size": 10,
            "lfs": {"sha256": "test_sha256"},
        }
        mock_hf_file_system.return_value.open.return_value.__enter__.return_value = (
            MagicMock()
        )

        model.save()
        mock_hf_file_system.return_value.glob.assert_called()
        mock_hf_file_system.return_value.stat.assert_called()
        mock_hf_file_system.return_value.open.assert_called()
        mock_get_model_store.assert_called()
        mock_get_model_store().save_stream.assert_called()
        finish_mock.assert_called_once()

        model._save_single_file("file1")
        mock_hf_file_system.return_value.stat.assert_called_with("file1")
        mock_hf_file_system.return_value.open.assert_called_with("file1", "rb")
        mock_get_model_store().save_stream.assert_called()

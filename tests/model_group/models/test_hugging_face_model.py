import unittest
from unittest.mock import ANY, MagicMock, Mock, call, patch

from paka.kube_resources.model_group.models.base import MODEL_PATH_PREFIX
from paka.kube_resources.model_group.models.hugging_face_model import (
    HuggingFaceModel,  # replace with the actual module name
)
from paka.utils import to_yaml


class TestHuggingFaceModel(unittest.TestCase):
    def setUp(self) -> None:
        self.model = HuggingFaceModel(
            "TheBloke/Llama-2-7B-Chat-GGUF",
            files=[
                "llama-2-7b-chat.Q4_0.gguf",
                "llama-2-7b-chat.Q2_K.gguf",
            ],
        )

    @patch.object(HuggingFaceModel, "get_file_info")
    @patch.object(HuggingFaceModel, "logging_for_class")
    def test_validate_files(
        self, mock_logging_for_class: Mock, mock_get_file_info: Mock
    ) -> None:
        # Arrange
        self.model.fs = MagicMock()
        self.model.fs.glob = MagicMock()
        self.model.fs.glob.side_effect = [
            ["TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf"],
            ["TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q2_K.gguf"],
        ]
        mock_get_file_info.side_effect = [
            {"size": 100, "lfs": {"sha256": "abc123"}},
            {"size": 200, "lfs": {"sha256": "edb322"}},
        ]

        # Act
        self.model.validate_files()

        # Assert
        mock_logging_for_class.assert_not_called()

    @patch.object(HuggingFaceModel, "get_file_info")
    @patch.object(HuggingFaceModel, "logging_for_class")
    def test_validate_files_file_not_found(
        self, mock_logging_for_class: Mock, mock_get_file_info: Mock
    ) -> None:
        # Arrange
        self.model.fs = MagicMock()
        self.model.fs.glob = MagicMock()
        self.model.fs.glob.return_value = []

        # Act
        self.model.validate_files()

        # Assert
        self.assertEqual(mock_logging_for_class.call_count, 2)
        mock_get_file_info.assert_not_called()

    def test_get_file_info(self) -> None:
        # Arrange
        hf_file_path = "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf"
        expected_file_info = {"size": 100, "lfs": {"sha256": "abc123"}}
        self.model.fs = MagicMock()
        self.model.fs.stat = MagicMock()
        self.model.fs.stat.return_value = expected_file_info

        # Act
        file_info = self.model.get_file_info(hf_file_path)

        # Assert
        self.assertEqual(file_info, expected_file_info)
        self.model.fs.stat.assert_called_once_with(hf_file_path)

    @patch.object(HuggingFaceModel, "get_file_info")
    @patch.object(HuggingFaceModel, "download")
    def test_upload(self, mock_download: Mock, mock_get_file_info: Mock) -> None:
        # Arrange
        hf_file_path = "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf"
        hf_file = MagicMock()
        self.model.fs = MagicMock()
        self.model.fs.open = MagicMock()
        self.model.fs.open.return_value.__enter__.return_value = hf_file
        mock_download = MagicMock()
        mock_get_file_info.return_value = {"size": 100, "lfs": {"sha256": "abc123"}}
        sha256 = "abc123"

        # Act
        self.model.upload(hf_file_path)

        # Assert
        self.model.fs.open.assert_called_once_with(hf_file_path, "rb")
        mock_download.assert_called_once_with(hf_file_path, hf_file, 100, sha256)

    @patch("boto3.resource")
    @patch("paka.utils.to_yaml")
    @patch.object(HuggingFaceModel, "logging_for_class")
    def test_save_manifest_yml(
        self,
        mock_logging_for_class: Mock,
        mock_to_yaml: Mock,
        mock_boto3_resource: Mock,
    ) -> None:
        # Arrange
        self.model.completed_files = [
            ("TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf", "abc123"),
            ("TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q2_K.gguf", "edb322"),
        ]
        self.model.s3_bucket = "my-bucket"
        mock_s3_resource = mock_boto3_resource.return_value
        mock_s3_object = mock_s3_resource.Object.return_value

        # Act
        self.model.save_manifest_yml()

        # Assert
        expected_manifest = {
            "repo_id": "TheBloke/Llama-2-7B-Chat-GGUF",
            "files": [
                ("TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf", "abc123"),
                ("TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q2_K.gguf", "edb322"),
            ],
            "inference_devices": ["cpu"],
            "quantization": "GPTQ",
            "runtime": "llama.cpp",
            "prompt_template": "chatml",
        }

        expected_manifest_yml = to_yaml(expected_manifest)
        mock_s3_object.put.assert_called_once_with(Body=expected_manifest_yml)
        mock_logging_for_class.assert_called_once_with(
            f"manifest.yml file saved to {MODEL_PATH_PREFIX}/TheBloke/Llama-2-7B-Chat-GGUF/manifest.yml"
        )

    @patch("concurrent.futures.wait")
    @patch.object(HuggingFaceModel, "logging_for_class")
    @patch.object(HuggingFaceModel, "validate_files")
    @patch.object(HuggingFaceModel, "create_pbar")
    @patch.object(HuggingFaceModel, "upload")
    @patch.object(HuggingFaceModel, "handle_upload_completion")
    def test_upload_files(
        self,
        mock_handle_upload_completion: Mock,
        mock_upload: Mock,
        mock_create_pbar: Mock,
        mock_validate_files: Mock,
        mock_logging_for_class: Mock,
        mock_wait: Mock,
    ) -> None:
        # Arrange
        self.model.files = [
            "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf",
            "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q2_K.gguf",
        ]

        # Act
        self.model.upload_files()

        # Assert
        mock_logging_for_class.assert_called_once_with("Uploading files to S3...")
        mock_validate_files.assert_called_once()
        self.assertEqual(mock_upload.call_count, 2)
        mock_handle_upload_completion.assert_called_once()

    @patch.object(HuggingFaceModel, "logging_for_class")
    @patch.object(HuggingFaceModel, "save_manifest_yml")
    @patch.object(HuggingFaceModel, "clear_counter")
    @patch.object(HuggingFaceModel, "close_pbar")
    def test_handle_upload_completion(
        self,
        mock_close_pbar: Mock,
        mock_clear_counter: Mock,
        mock_save_manifest_yml: Mock,
        mock_logging_for_class: Mock,
    ) -> None:
        # Arrange
        self.model.completed_files = [
            ("TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf", "abc123"),
            ("TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q2_K.gguf", "edb322"),
        ]
        mock_logging_for_class = MagicMock()

        # Act
        self.model.handle_upload_completion()

        # Assert
        mock_save_manifest_yml.assert_called_once()
        self.assertEqual(self.model.completed_files, [])
        mock_clear_counter.assert_called_once()
        mock_close_pbar.assert_called_once()
        mock_logging_for_class.assert_called_once_with("All files have been uploaded.")

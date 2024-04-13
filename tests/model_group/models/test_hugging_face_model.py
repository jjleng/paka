import unittest
from unittest.mock import ANY, MagicMock, Mock, patch

from paka.kube_resources.model_group.models.hugging_face_model import (
    HuggingFaceModel,  # replace with the actual module name
)


class TestHuggingFaceModel(unittest.TestCase):
    def setUp(self) -> None:
        self.model = HuggingFaceModel(
            "TheBloke/Llama-2-7B-Chat-GGUF",
            files=[
                "llama-2-7b-chat.Q4_0.gguf",
                "llama-2-7b-chat.Q2_K.gguf",
            ],
        )

    @patch.object(HuggingFaceModel, "upload_fs_to_s3")
    @patch.object(HuggingFaceModel, "s3_file_exists")
    @patch.object(HuggingFaceModel, "save_manifest_yml")
    @patch.object(HuggingFaceModel, "pbar")
    def test_upload_file_to_s3(
        self,
        mock_pbar: Mock,
        mock_save_manifest_yml: Mock,
        mock_s3_file_exists: Mock,
        mock_upload_fs_to_s3: Mock,
    ) -> None:
        mock_s3_file_exists.return_value = False
        mock_upload_fs_to_s3.return_value = (
            "9958ee9b670594147b750bbc7d0540b928fa12dcc5dd4c58cc56ed2eb85e371b"
        )

        hf_file_path = "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf"
        full_model_file_path = self.model.get_s3_file_path(hf_file_path)
        mock_pbar = MagicMock()
        mock_pbar.postfix = MagicMock()

        # Act
        self.model.s3 = MagicMock()
        self.model.s3.create_multipart_upload = MagicMock()
        self.model.s3.create_multipart_upload.return_value = {"UploadId": "test"}
        self.model.files_sha256[hf_file_path] = (
            "9958ee9b670594147b750bbc7d0540b928fa12dcc5dd4c58cc56ed2eb85e371b"
        )
        self.model.upload_file_to_s3(hf_file_path)

        # Assert
        mock_upload_fs_to_s3.assert_called_once_with(ANY, full_model_file_path, "test")

    @patch.object(HuggingFaceModel, "upload_file_to_s3")
    @patch.object(HuggingFaceModel, "save_manifest_yml")
    @patch.object(HuggingFaceModel, "validate_files")
    @patch.object(HuggingFaceModel, "create_pbar")
    @patch.object(HuggingFaceModel, "close_pbar")
    def test_upload_files(
        self,
        mock_close_pbar: Mock,
        mock_create_pbar: Mock,
        mock_validate_files: Mock,
        mock_save_manifest_yml: Mock,
        mock_upload_file_to_s3: Mock,
    ) -> None:
        # Act
        self.model.files = ["file1", "file2"]
        self.model.upload_files()

        # Assert
        self.assertEqual(mock_upload_file_to_s3.call_count, 2)
        mock_upload_file_to_s3.assert_called_with(ANY)

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
        self.assertEqual(len(self.model.files_size), 2)
        self.assertEqual(len(self.model.files_sha256), 2)
        self.assertEqual(
            self.model.files_size,
            {
                "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf": 100,
                "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q2_K.gguf": 200,
            },
        )
        self.assertEqual(
            self.model.files_sha256,
            {
                "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf": "abc123",
                "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q2_K.gguf": "edb322",
            },
        )
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
        self.assertEqual(len(self.model.files_size), 0)
        self.assertEqual(len(self.model.files_sha256), 0)
        self.assertEqual(mock_logging_for_class.call_count, 2)
        mock_get_file_info.assert_not_called()

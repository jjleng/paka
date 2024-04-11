import unittest
from unittest.mock import ANY, MagicMock, Mock, patch

from paka.kube_resources.model_group.models.hugging_face_model import (
    HuggingFaceModel,  # replace with the actual module name
)


class TestHuggingFaceModel(unittest.TestCase):
    def setUp(self) -> None:
        with patch.object(HuggingFaceModel, "validate_files") as mock_validate_files:
            mock_validate_files.return_value = [
                "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf",
                "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q2_K.gguf",
            ]
            self.model = HuggingFaceModel(
                "TheBloke/Llama-2-7B-Chat-GGUF",
                files=[
                    "llama-2-7b-chat.Q4_0.gguf",
                    "llama-2-7b-chat.Q2_K.gguf",
                ],
            )

    @patch.object(HuggingFaceModel, "get_file_info")
    @patch.object(HuggingFaceModel, "upload_fs_to_s3")
    @patch.object(HuggingFaceModel, "s3_file_exists")
    @patch.object(HuggingFaceModel, "save_manifest_yml")
    def test_upload_file_to_s3(
        self,
        mock_save_manifest_yml: Mock,
        mock_s3_file_exists: Mock,
        mock_upload_fs_to_s3: Mock,
        mock_get_file_info: Mock,
    ) -> None:
        mock_s3_file_exists.return_value = False
        mock_upload_fs_to_s3.return_value = (
            "9958ee9b670594147b750bbc7d0540b928fa12dcc5dd4c58cc56ed2eb85e371b"
        )

        hf_file_path = "TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf"
        full_model_file_path = self.model.get_s3_file_path(hf_file_path)
        mock_get_file_info.return_value = {
            "size": 1024,
            "lfs": {
                "sha256": (
                    "9958ee9b670594147b750bbc7d0540b928fa12dcc5dd4c58cc56ed2eb85e371b"
                )
            },
        }

        # Act
        self.model.s3 = MagicMock()
        self.model.s3.create_multipart_upload = MagicMock()
        self.model.s3.create_multipart_upload.return_value = {"UploadId": "test"}
        self.model.upload_file_to_s3(hf_file_path)

        # Assert
        mock_get_file_info.assert_called_once_with(hf_file_path)
        mock_upload_fs_to_s3.assert_called_once_with(
            ANY, 1024, full_model_file_path, "test"
        )

    @patch.object(HuggingFaceModel, "upload_file_to_s3")
    @patch.object(HuggingFaceModel, "save_manifest_yml")
    def test_upload_files(
        self, mock_save_manifest_yml: Mock, mock_upload_file_to_s3: Mock
    ) -> None:
        # Act
        self.model.upload_files()

        # Assert
        self.assertEqual(mock_upload_file_to_s3.call_count, 2)
        mock_upload_file_to_s3.assert_called_with(ANY)

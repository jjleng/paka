import unittest
from unittest.mock import Mock, patch

from paka.kube_resources.model_group.models.hugging_face_model import (
    HuggingFaceModel,  # replace with the actual module name
)


class TestHuggingFaceModel(unittest.TestCase):
    def test_define_urls(self) -> None:
        # Arrange
        model = HuggingFaceModel(
            "TheBloke/Llama-2-7B-Chat-GGUF",
            files=[
                (
                    "llama-2-7b-chat.Q4_0.gguf",
                    "9958ee9b670594147b750bbc7d0540b928fa12dcc5dd4c58cc56ed2eb85e371b",
                ),
                (
                    "llama-2-7b-chat.Q2_K.gguf",
                    "c0dd304d761e8e05d082cc2902d7624a7f87858fdfaa4ef098330ffe767ff0d3",
                ),
            ],
        )
        for url in model.urls:
            self.assertIn("https", url)
        self.assertEqual(len(model.urls), len(model.sha256s))

    @patch.object(HuggingFaceModel, "download_all")
    def test_save_to_s3(self, mock_download_all: Mock) -> None:
        """
        Test case for the download method of the HuggingFaceModel class.

        This test verifies that the download method correctly calls the `download_all` method
        with the appropriate URLs and SHA256 hashes.

        Args:
            mock_download_all (Mock): A mock object representing the `download_all` method.

        Returns:
            None
        """
        # Arrange
        model = HuggingFaceModel(
            "TheBloke/Llama-2-7B-Chat-GGUF",
            files=[
                (
                    "llama-2-7b-chat.Q4_0.gguf",
                    "9958ee9b670594147b750bbc7d0540b928fa12dcc5dd4c58cc56ed2eb85e371b",
                ),
                (
                    "llama-2-7b-chat.Q2_K.gguf",
                    "c0dd304d761e8e05d082cc2902d7624a7f87858fdfaa4ef098330ffe767ff0d3",
                ),
            ],
        )

        # Act
        model.save_to_s3()

        # Assert
        mock_download_all.assert_called_once_with(model.urls, model.sha256s)

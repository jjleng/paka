import unittest
from unittest.mock import ANY, MagicMock, Mock, patch

from paka.kube_resources.model_group.models.base import Model


class TestModel(unittest.TestCase):
    def setUp(self) -> None:
        self.model = Model("TheBloke/Llama-2-7B-Chat-GGUF")

    @patch("paka.kube_resources.model_group.models.base.read_current_cluster_data")
    @patch("paka.kube_resources.model_group.models.base.boto3.client")
    def test_init(
        self, mock_boto3_client: Mock, mock_read_current_cluster_data: Mock
    ) -> None:
        mock_read_current_cluster_data.return_value = "test_bucket"
        self.model = Model(
            "TheBloke/Llama-2-7B-Chat-GGUF",
            download_max_concurrency=5,
            s3_chunk_size=4 * 1024 * 1024,
            s3_max_concurrency=10,
        )
        self.assertEqual(self.model.name, "TheBloke/Llama-2-7B-Chat-GGUF")
        self.assertEqual(self.model.s3_bucket, "test_bucket")
        self.assertEqual(self.model.s3_chunk_size, 4 * 1024 * 1024)
        self.assertEqual(self.model.download_max_concurrency, 5)
        self.assertEqual(self.model.s3_max_concurrency, 10)
        mock_read_current_cluster_data.assert_called_once_with("bucket")
        # mock_boto3_client.assert_called_once_with("s3", config=MagicMock(signature_version="s3v4"))

    @patch("paka.kube_resources.model_group.models.base.logger")
    @patch("paka.kube_resources.model_group.models.base.requests.get")
    @patch("paka.kube_resources.model_group.models.base.Model.s3_file_exists")
    @patch("paka.kube_resources.model_group.models.base.Model.upload_part")
    @patch("paka.kube_resources.model_group.models.base.Model.upload_to_s3")
    def test_download(
        self,
        mock_upload_to_s3: Mock,
        mock_upload_part: Mock,
        mock_s3_file_exists: Mock,
        mock_requests_get: Mock,
        mock_logger: Mock,
    ) -> None:
        mock_s3_file_exists.return_value = False
        mock_upload_part.return_value = {"PartNumber": 1, "ETag": "test_etag"}
        mock_response = MagicMock()
        mock_response.headers.get.return_value = "100"
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_response.raise_for_status.return_value = True
        mock_requests_get.return_value.__enter__.return_value = mock_response
        url = "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_0.gguf"
        sha256 = "9958ee9b670594147b750bbc7d0540b928fa12dcc5dd4c58cc56ed2eb85e371b"
        mock_upload_to_s3.return_value = ("test_upload_id", sha256)
        self.model.download(url, sha256)
        mock_s3_file_exists.assert_called_once_with(
            "models/TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf"
        )
        mock_logger.info.assert_called_with(f"Downloading model from {url}")
        mock_requests_get.assert_called_once_with(url, stream=True)
        mock_response.raise_for_status.assert_called_once()
        mock_upload_to_s3.assert_called_once_with(
            mock_response,
            "models/TheBloke/Llama-2-7B-Chat-GGUF/llama-2-7b-chat.Q4_0.gguf",
        )

    @patch.object(Model, "download")
    def test_download_all(self, mock_download: Mock) -> None:
        urls = [
            "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_0.gguf",
            "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q2_K.gguf",
        ]
        sha256s: list[str | None] = [
            "9958ee9b670594147b750bbc7d0540b928fa12dcc5dd4c58cc56ed2eb85e371b",
            None,
        ]

        self.model.download_all(urls, sha256s)
        self.assertEqual(mock_download.call_count, 2)
        mock_download.assert_called_with(ANY, ANY)

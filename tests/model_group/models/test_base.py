import unittest
from unittest.mock import ANY, MagicMock, Mock, patch

import requests

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

    @patch("paka.kube_resources.model_group.models.base.read_current_cluster_data")
    @patch("paka.kube_resources.model_group.models.base.boto3.client")
    @patch("paka.kube_resources.model_group.models.base.requests")
    @patch.object(Model, "upload_to_s3")
    @patch.object(Model, "s3_file_exists")
    def test_download(
        self,
        mock_s3_file_exists: Mock,
        mock_upload_to_s3: Mock,
        mock_requests: Mock,
        mock_boto3_client: Mock,
        mock_read_current_cluster_data: Mock,
    ) -> None:
        mock_s3_file_exists.return_value = False
        mock_read_current_cluster_data.return_value = "test_bucket"
        self.model = Model("TheBloke/Llama-2-7B-Chat-GGUF")
        url = "https://example.com/model_file.txt"
        response = MagicMock(spec=requests.Response)
        response.iter_content.return_value = [b"chunk1", b"chunk2", b"chunk3"]
        total_size = 9
        self.model.download(url, response, total_size)
        mock_boto3_client.assert_called_once_with("s3", config=ANY)
        mock_read_current_cluster_data.assert_called_once_with("bucket")
        mock_upload_to_s3.assert_called_once_with(
            response, "models/TheBloke/Llama-2-7B-Chat-GGUF/model_file.txt", ANY
        )

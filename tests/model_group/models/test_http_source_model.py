import unittest
from unittest.mock import Mock, call, patch

from paka.kube_resources.model_group.models.http_source_model import HttpSourceModel


class TestHttpSourceModel(unittest.TestCase):
    def setUp(self) -> None:
        self.urls = ["http://example.com/file1.txt", "http://example.com/file2.txt"]
        self.model = HttpSourceModel("test_model", self.urls)

    def test_str(self) -> None:
        self.assertEqual(str(self.model), "HttpSourceModel")

    @patch(
        "paka.kube_resources.model_group.models.http_source_model.HttpSourceManifest"
    )
    @patch("paka.kube_resources.model_group.models.http_source_model.to_yaml")
    @patch("paka.kube_resources.model_group.models.http_source_model.boto3.resource")
    def test_save_manifest_yml(
        self,
        mock_boto3_resource: Mock,
        mock_to_yaml: Mock,
        mock_HttpSourceManifest: Mock,
    ) -> None:
        mock_manifest = mock_HttpSourceManifest.return_value
        mock_to_yaml.return_value = "manifest_yaml"
        self.model.s3_bucket = "test_bucket"
        mock_s3_object = mock_boto3_resource.return_value.Object.return_value
        self.model.save_manifest_yml()
        mock_HttpSourceManifest.assert_called_once_with(
            name="test_model",
            urls=[],
            inference_devices=["cpu"],
            quantization="GPTQ",
            runtime="llama.cpp",
            prompt_template="chatml",
        )
        mock_to_yaml.assert_called_once_with(
            mock_manifest.model_dump(exclude_none=True)
        )
        mock_boto3_resource.assert_called_once_with("s3")
        mock_s3_object.put.assert_called_once_with(Body="manifest_yaml")

    @patch("paka.kube_resources.model_group.models.http_source_model.requests.get")
    @patch.object(HttpSourceModel, "download")
    def test_upload(self, mock_download: Mock, mock_requests_get: Mock) -> None:
        mock_response = mock_requests_get.return_value
        mock_response.headers.get.return_value = "100"
        self.model.upload("http://example.com/file.txt")
        mock_requests_get.assert_called_once_with(
            "http://example.com/file.txt", stream=True
        )

    @patch(
        "paka.kube_resources.model_group.models.http_source_model.concurrent.futures.ThreadPoolExecutor"
    )
    @patch("concurrent.futures.wait")
    @patch.object(HttpSourceModel, "upload")
    @patch.object(HttpSourceModel, "handle_upload_completion")
    def test_upload_files(
        self,
        mock_handle_upload_completion: Mock,
        mock_upload: Mock,
        mock_wait: Mock,
        mock_ThreadPoolExecutor: Mock,
    ) -> None:
        mock_executor = mock_ThreadPoolExecutor.return_value
        mock_future1 = Mock()
        mock_future2 = Mock()
        mock_executor.submit.side_effect = [mock_future1, mock_future2]
        self.model.upload_files()
        mock_ThreadPoolExecutor.assert_called_once_with(max_workers=10)
        mock_future1.result.assert_not_called()
        mock_future2.result.assert_not_called()
        mock_handle_upload_completion.assert_called_once()

    @patch(
        "paka.kube_resources.model_group.models.http_source_model.HttpSourceModel.save_manifest_yml"
    )
    @patch.object(HttpSourceModel, "clear_counter")
    @patch.object(HttpSourceModel, "close_pbar")
    @patch.object(HttpSourceModel, "logging_for_class")
    def test_handle_upload_completion(
        self,
        mock_logging_for_class: Mock,
        mock_close_pbar: Mock,
        mock_clear_counter: Mock,
        mock_save_manifest_yml: Mock,
    ) -> None:
        self.model.completed_files = []
        self.model.handle_upload_completion()
        mock_save_manifest_yml.assert_called_once()
        self.assertEqual(self.model.completed_files, [])
        mock_clear_counter.assert_called_once()
        mock_close_pbar.assert_called_once()
        mock_logging_for_class.assert_called_once_with("All files have been uploaded.")


if __name__ == "__main__":
    unittest.main()

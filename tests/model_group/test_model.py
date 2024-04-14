import hashlib
from unittest.mock import ANY, MagicMock, patch

import pytest

from paka.kube_resources.model_group.model import (
    delete_s3_file,
    download_file_to_s3,
    download_model,
    get_model_file_name,
)
from paka.kube_resources.model_group.supported_models import SUPPORTED_MODELS


def test_delete_s3_file_exists() -> None:
    with patch("boto3.client") as mock_client, patch(
        "paka.kube_resources.model_group.model.s3_file_exists", return_value=True
    ) as mock_exists:
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3

        delete_s3_file("test-bucket", "test-file")

        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="test-file"
        )


def test_delete_s3_file_not_exists() -> None:
    with patch("boto3.client") as mock_client, patch(
        "paka.kube_resources.model_group.model.s3_file_exists", return_value=False
    ) as mock_exists:
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3

        delete_s3_file("test-bucket", "test-file")

        mock_s3.delete_object.assert_not_called()


def test_download_file_to_s3() -> None:
    with patch("requests.get") as mock_get, patch("boto3.client") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "1024"}
        mock_response.iter_content.return_value = iter([b"test"] * 1024)
        mock_get.return_value.__enter__.return_value = mock_response

        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3
        mock_s3.create_multipart_upload.return_value = {"UploadId": "test"}
        mock_s3.complete_multipart_upload.return_value = {}

        sha256_value = download_file_to_s3(
            "http://test.com", "test-bucket", "test-file"
        )

        mock_get.assert_called_once_with("http://test.com", stream=True)
        mock_client.assert_called_once_with("s3", config=ANY)
        mock_s3.create_multipart_upload.assert_called_once_with(
            Bucket="test-bucket", Key="test-file"
        )
        mock_s3.complete_multipart_upload.assert_called_once()

        assert sha256_value == hashlib.sha256(b"test" * 1024).hexdigest()


def test_download_model() -> None:
    with patch(
        "paka.kube_resources.model_group.model.s3_file_prefix_exists",
        return_value=False,
    ) as mock_exists, patch(
        "paka.kube_resources.model_group.model.download_file_to_s3",
        return_value=SUPPORTED_MODELS["mistral-7b"].sha256,
    ) as mock_download, patch(
        "paka.kube_resources.model_group.model.delete_s3_file"
    ) as mock_delete, patch(
        "paka.kube_resources.model_group.model.save_string_to_s3"
    ) as mock_save:
        download_model("mistral-7b")

        mock_exists.assert_called_once()
        mock_download.assert_called_once()
        mock_delete.assert_not_called()
        mock_save.assert_called_once()


def test_get_model_file_name_supported() -> None:
    for model_name in SUPPORTED_MODELS:
        result = get_model_file_name(model_name)

        expected_model_name = SUPPORTED_MODELS[model_name].url.split("/")[-1]
        assert result == expected_model_name


def test_get_model_file_name_not_supported() -> None:
    with pytest.raises(Exception) as e:
        get_model_file_name("unsupported")

    assert str(e.value) == "Model unsupported is not supported."

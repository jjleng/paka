from unittest.mock import MagicMock, patch

import paka.model.http_model
from paka.model.http_model import BaseMLModel, HttpSourceModel


def test_http_source_model() -> None:
    with patch.object(
        paka.model.http_model.requests, "get"
    ) as mock_requests_get, patch.object(
        BaseMLModel, "get_model_store", return_value=MagicMock()
    ) as mock_get_model_store, patch.object(
        BaseMLModel,
        "finish",
        return_value=MagicMock(),
    ) as finish_mock:
        model = HttpSourceModel(
            name="TestModel",
            urls=["http://example.com/file1", "http://example.com/file2"],
            quantization="GPTQ",
            prompt_template_name=None,
            prompt_template_str=None,
        )

        mock_response = MagicMock()
        mock_response.headers.get.return_value = 10
        mock_requests_get.return_value.__enter__.return_value = mock_response

        model.save()
        mock_requests_get.assert_called()
        mock_get_model_store.assert_called()
        mock_get_model_store().save_stream.assert_called()
        finish_mock.assert_called_once()

        model._save_single_url("http://example.com/file1")
        mock_requests_get.assert_called_with("http://example.com/file1", stream=True)
        mock_get_model_store().save_stream.assert_called()

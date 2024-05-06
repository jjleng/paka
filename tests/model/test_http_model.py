from unittest.mock import MagicMock, patch

import paka.model.http_model
from paka.model.http_model import BaseMLModel, HttpSourceModel


def test_http_source_model() -> None:
    with patch.object(
        paka.model.http_model.requests, "get"
    ) as mock_requests_get, patch.object(
        BaseMLModel,
        "finish",
        return_value=MagicMock(),
    ) as finish_mock:
        model_store_mock = MagicMock()
        model = HttpSourceModel(
            name="TestModel",
            urls=["http://example.com/file1", "http://example.com/file2"],
            model_store=model_store_mock,
            quantization="GPTQ",
            prompt_template_name=None,
            prompt_template_str=None,
        )

        mock_response = MagicMock()
        mock_response.headers.get.return_value = 10
        mock_requests_get.return_value.__enter__.return_value = mock_response

        model.save()
        mock_requests_get.assert_called()
        model_store_mock.save_stream.assert_called()
        finish_mock.assert_called_once()

        model._save_single_url("http://example.com/file1")
        mock_requests_get.assert_called_with("http://example.com/file1", stream=True)
        model_store_mock.save_stream.assert_called()

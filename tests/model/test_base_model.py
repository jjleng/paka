import io
from unittest.mock import MagicMock, patch

from paka.model.base_model import BaseMLModel


class ConcreteMLModel(BaseMLModel):
    def save(self) -> None:
        pass


def test_base_ml_model() -> None:

    progress_bar_mock = MagicMock()
    model_store_mock = MagicMock(progress_bar=progress_bar_mock)
    model = ConcreteMLModel(
        name="TestModel",
        model_store=model_store_mock,
        quantization="GPTQ",
        prompt_template_name=None,
        prompt_template_str=None,
    )

    model.save_manifest_yml()
    model_store_mock.save.assert_called_once()

    stream = io.BytesIO(b"Test data")

    model.save_single_stream("test.txt", stream, 9, "test_sha256")
    model_store_mock.save_stream.assert_called_with(
        "test.txt", stream, 9, "test_sha256"
    )
    assert ("test.txt", "test_sha256") in model.completed_files

    model.finish()
    progress_bar_mock.close_progress_bar.assert_called_once()

import pytest

from paka.model.settings import ModelSettings


def test_validate_inference_devices() -> None:
    settings = ModelSettings(
        inference_devices=["cpu", "gpu"], quantization="GPTQ", runtime="llama.cpp"
    )
    assert settings.inference_devices == ["cpu", "gpu"]

    with pytest.raises(ValueError):
        ModelSettings(
            inference_devices=["invalid_device"],
            quantization="GPTQ",
            runtime="llama.cpp",
        )


def test_validate_quantization() -> None:
    settings = ModelSettings(
        inference_devices=["cpu"], quantization="GPTQ", runtime="llama.cpp"
    )
    assert settings.quantization == "GPTQ"

    with pytest.raises(ValueError):
        ModelSettings(
            inference_devices=["cpu"],
            quantization="invalid_quantization",
            runtime="llama.cpp",
        )


def test_validate_runtime() -> None:
    settings = ModelSettings(
        inference_devices=["cpu"], quantization="GPTQ", runtime="llama.cpp"
    )
    assert settings.runtime == "llama.cpp"

    with pytest.raises(ValueError):
        ModelSettings(
            inference_devices=["cpu"], quantization="GPTQ", runtime="invalid_runtime"
        )


def test_validate_prompt_template_name() -> None:
    settings = ModelSettings(
        inference_devices=["cpu"],
        quantization="GPTQ",
        runtime="llama.cpp",
        prompt_template_name="chatml",
    )
    assert settings.prompt_template_name == "chatml"

    with pytest.raises(ValueError):
        ModelSettings(
            inference_devices=["cpu"],
            quantization="GPTQ",
            runtime="llama.cpp",
            prompt_template_name="invalid_template",
        )

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ModelSettings(BaseModel):
    inference_devices: list[str] = Field(
        description="The list of inference devices (cpu, gpu, tpu, etc) to use.",
    )
    quantization: str = Field(
        description="The quantization method (GPTQ, AWQ, GGUF_Q4_0, etc) to use."
    )
    runtime: str = Field(
        description="The runtime (llama.cpp, vLLM, pytorch, etc) to use."
    )
    prompt_template_name: Optional[str] = Field(
        None, description="The prompt template (chatml, llama-2, gemma, etc) to use."
    )
    prompt_template_str: Optional[str] = Field(
        None, description="The prompt template string to use."
    )

    @field_validator("inference_devices")
    def validate_inference_devices(cls, v: List[str]) -> List[str]:
        valid_devices = ["cpu", "gpu"]
        if not all(device in valid_devices for device in v):
            raise ValueError("Invalid inference device")
        return v

    @field_validator("quantization")
    def validate_quantization(cls, v: str) -> str:
        valid_methods = [
            "GPTQ",
            "AWQ",
            "GGUF_Q2_K",
            "GGUF_Q3_K_L",
            "GGUF_Q3_K_M",
            "GGUF_Q3_K_S",
            "GGUF_Q4_0",
            "GGUF_Q4_K_M",
            "GGUF_Q4_K_S",
            "GGUF_Q5_0",
            "GGUF_Q5_K_M",
            "GGUF_Q5_K_S",
            "GGUF_Q6_K",
            "GGUF_Q8_0",
        ]
        if v not in valid_methods:
            raise ValueError("Invalid quantization method")
        return v

    @field_validator("runtime")
    def validate_runtime(cls, v: str) -> str:
        valid_runtimes = ["llama.cpp"]
        if v not in valid_runtimes:
            raise ValueError("Invalid runtime")
        return v

    @field_validator("prompt_template_name")
    def validate_prompt_template_name(cls, v: str) -> str:
        valid_templates = [
            "chatml",
            "llama-2",
            "gemma",
            "alpaca",
            "qwen",
            "vicuna",
            "oasst_llama",
            "baichuan-2",
            "baichuan",
            "openbuddy",
            "redpajama-incite",
            "snoozy",
            "phind",
            "intel",
            "open-orca",
            "mistrallite",
            "zephyr",
            "pygmalion",
            "mistral-instruct",
            "chatglm3",
            "openchat",
            "saiga",
        ]
        if v is not None and v not in valid_templates:
            raise ValueError("Invalid prompt template name")
        return v

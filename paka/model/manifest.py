from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class ModelFile(BaseModel):
    name: str
    sha256: str


class ModelManifest(BaseModel):
    """
    A manifest for a model. The manifest is stored along with the model files.

    Attributes:
        name (str): The name of the model.
        files (List[ModelFile]): A list of model file where each model file contains a file name and a hash.
        inference_devices (List[str]): The list of inference devices (cpu, gpu, tpu, etc) the model can run on.
        quantization (str): The quantization method (GPTQ, AWQ, GGUF_Q4_0, etc) the model uses.
        runtime (str): The runtime (llama.cpp, vLLM, pytorch, etc) the model uses.
        prompt_template_name (Optional[str]): The prompt template name (chatml, llama-2, gemma, etc) the model uses. This field is optional.
        prompt_template_str (Optional[str]): The prompt template string the model uses. This field is optional.
        main_model (Optional[str]): The main model file name. This field is optional.
        clip_model (Optional[str]): The clip model file name. This field is optional and is used for multimodal models.
        lora_model (Optional[str]): The lora model file name. This field is optional.
    """

    name: str
    files: List[ModelFile]
    inference_devices: List[str]
    quantization: str
    runtime: str
    prompt_template_str: Optional[str]
    prompt_template_name: Optional[str]

    main_model: Optional[str] = None
    # Clip model is used for multimodal models
    clip_model: Optional[str] = None
    lora_model: Optional[str] = None

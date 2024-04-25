from __future__ import annotations

import os
import re
from typing import List, Optional

from huggingface_hub import HfFileSystem
from huggingface_hub.utils import validate_repo_id

from paka.config import CloudModelGroup
from paka.model.base_model import BaseMLModel


# Heuristic to determine if the image is a llama.cpp image
def is_llama_cpp_image(image: str) -> bool:
    return "llama.cpp" in image.lower()


def get_model_file_from_model_store(
    model_group: CloudModelGroup,
) -> Optional[str]:
    if model_group.model and model_group.model.useModelStore:
        store = BaseMLModel.get_model_store(with_progress_bar=False)
        # Find the file that ends with .gguf or .ggml from directory /data
        model_files = [
            file
            for file in store.glob(f"{model_group.name}/*")
            if re.search(r"\.(gguf|ggml)$", file, re.IGNORECASE)
        ]

        if not model_files:
            model_files = [
                file
                for file in store.glob(f"{model_group.name}/*")
                if any(
                    re.match(file_pattern, file)
                    for file_pattern in model_group.model.files
                )
            ]

        if len(model_files) > 1:
            raise ValueError("Multiple model files found in /data directory.")

        if len(model_files) == 1:
            return os.path.basename(model_files[0])

    return None


def get_runtime_command_llama_cpp(model_group: CloudModelGroup) -> List[str]:
    runtime = model_group.runtime
    if runtime.command:
        command_str = " ".join(runtime.command) if runtime.command else ""
        # If the command knows where or how to load the model file, we don't need to do anything.
        if (
            re.search(r"(--model|-m)[ \t]*\S+", command_str)
            or (
                re.search(r"--hf-repo|-hfr", command_str)
                and re.search(r"--hf-file|-hff", command_str)
            )
            or re.search(r"--model-url|-mu[ \t]*\S+", command_str)
        ):
            return runtime.command

    model_file = get_model_file_from_model_store(model_group)

    def attach_model_to_command(command: List[str]) -> List[str]:
        if model_file:
            return command + ["--model", f"/data/{model_file}"]
        elif model_group.model and model_group.model.hfRepoId:

            validate_repo_id(model_group.model.hfRepoId)
            hf_fs = HfFileSystem()
            files = [
                file
                for pattern in model_group.model.files
                for file in hf_fs.glob(f"{model_group.model.hfRepoId}/{pattern}")
            ]

            if len(files) > 1:
                raise ValueError("Multiple model files found in HuggingFace repo.")
            if len(files) == 0:
                raise ValueError("No model file found in HuggingFace repo.")

            return command + [
                "--hf-repo",
                model_group.model.hfRepoId,
                "--hf-file",
                model_group.model.files[0],
            ]
        else:
            raise ValueError("Did not find a model to load.")

    if runtime.command:
        return attach_model_to_command(runtime.command)

    # https://github.com/ggerganov/llama.cpp/tree/master/examples/server
    command = [
        "/server",
        "--host",
        "0.0.0.0",
        "--parallel",  # Number of parallel requests to handle
        "4",
        "--cont-batching",  # Enable continuous batching
        "--ctx-size",  # Total KV size of the context. On avg, each slot/client can process 32768/32 = 1024 tokens
        "8192",
        "--batch-size",  # Maximum number of tokens to decode in a batch
        "2048",
        "--ubatch-size",  # Physical batch size
        "512",
        "--n-predict",  # Maximum number of tokens to predict.
        "-1",
    ]

    if model_group.awsGpu:
        # The value 999 is typically sufficient for most models, as it attempts to offload as many layers as possible to the GPU.
        # However, for particularly large models, this may result in exceeding the GPU's memory capacity and cause errors.
        # A more effective approach would be to conduct a series of experiments with varying values for --n-gpu-layers to find the optimal setting.
        command.extend(["--n-gpu-layers", "999"])

    return attach_model_to_command(command)

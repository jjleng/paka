from __future__ import annotations

import os
import re
from typing import List, Optional

from huggingface_hub import HfFileSystem
from huggingface_hub.utils import validate_repo_id

from paka.cluster.context import Context
from paka.cluster.utils import get_model_store
from paka.config import CloudModelGroup
from paka.constants import MODEL_MOUNT_PATH


# Heuristic to determine if the image is a llama.cpp image
def is_llama_cpp_image(image: str) -> bool:
    return "llama.cpp" in image.lower()


def get_model_file_from_model_store(
    ctx: Context,
    model_group: CloudModelGroup,
) -> Optional[str]:
    if model_group.model and model_group.model.useModelStore:
        store = get_model_store(ctx, with_progress_bar=False)
        # Find the file that ends with .gguf or .ggml
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
            raise ValueError(
                f"Multiple model files found in {model_group.name}/ directory."
            )

        if len(model_files) == 1:
            return os.path.basename(model_files[0])

    return None


def get_runtime_command_llama_cpp(
    ctx: Context, model_group: CloudModelGroup
) -> List[str]:
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

    model_file = get_model_file_from_model_store(ctx, model_group)

    def attach_model_to_command(command: List[str]) -> List[str]:
        if model_file:
            return command + ["--model", f"{MODEL_MOUNT_PATH}/{model_file}"]
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

            hf_file = os.path.basename(files[0])

            return command + [
                "--hf-repo",
                model_group.model.hfRepoId,
                "--hf-file",
                hf_file,
                "--model",
                os.path.basename(
                    hf_file
                ),  # This is the model file name that the huggingface model is saved as
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
        "1",
        "--cont-batching",  # Enable continuous batching
        "--ctx-size",
        "4096",
        "--batch-size",  # Maximum number of tokens to decode in a batch
        "512",
        "--ubatch-size",  # Physical batch size
        "512",
        "--n-predict",  # Maximum number of tokens to predict.
        "-1",
        "--embedding",
        "--flash-attn",  # Enable flash attention
        "--metrics",  # Enable metrics
    ]

    if hasattr(model_group, "gpu") and model_group.gpu and model_group.gpu.enabled:
        # The value 999 is typically sufficient for most models, as it attempts to offload as many layers as possible to the GPU.
        # However, for particularly large models, this may result in exceeding the GPU's memory capacity and cause errors.
        # A more effective approach would be to conduct a series of experiments with varying values for --n-gpu-layers to find the optimal setting.
        command.extend(["--n-gpu-layers", "999"])

    return attach_model_to_command(command)

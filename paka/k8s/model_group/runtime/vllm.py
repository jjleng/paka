from __future__ import annotations

import re
import shlex
from typing import List

from huggingface_hub.utils import validate_repo_id

from paka.cluster.context import Context
from paka.cluster.utils import get_model_store
from paka.config import CloudModelGroup
from paka.constants import MODEL_MOUNT_PATH
from paka.k8s.utils import get_gpu_count


# Heuristic to determine if the image is a vLLM image
def is_vllm_image(image: str) -> bool:
    return image.lower().startswith("vllm")


def get_runtime_command_vllm(ctx: Context, model_group: CloudModelGroup) -> List[str]:
    runtime = model_group.runtime
    if runtime.command:
        command_str = " ".join(runtime.command) if runtime.command else ""
        if re.search(r"(--model)[ \t]*\S+", command_str):
            return runtime.command

    if model_group.model:
        if model_group.model.useModelStore:
            store = get_model_store(ctx, with_progress_bar=False)
            if not store.glob(f"{model_group.name}/*"):
                raise ValueError(
                    f"No model named {model_group.name} was found in the model store."
                )
            model_to_load = f"{MODEL_MOUNT_PATH}"
        elif model_group.model.hfRepoId:
            validate_repo_id(model_group.model.hfRepoId)
            model_to_load = model_group.model.hfRepoId
        else:
            raise ValueError("Did not find a model to load.")

    def attach_model_to_command(command: List[str]) -> List[str]:
        return command + ["--model", model_to_load]

    if runtime.command:
        return attach_model_to_command(runtime.command)

    command = shlex.split("python3 -O -u -m vllm.entrypoints.api_server --host 0.0.0.0")

    gpu_count = get_gpu_count(ctx, model_group)

    if gpu_count > 1:
        command += ["--tensor-parallel-size", str(gpu_count)]

    return attach_model_to_command(command)

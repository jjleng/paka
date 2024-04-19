from __future__ import annotations

from typing import List, Optional, Tuple

from typing_extensions import TypeAlias

from paka.model.hf_model import HuggingFaceModel

Pair: TypeAlias = Tuple[str, str]

# Jinja2 templates for prompt generation
prompt_templates = {
    "llama-2": """
[INST] <<SYS>>
{% if system %}
{{system}}
{% else %}
You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, while being safe.  Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content. Please ensure that your responses are socially unbiased and positive in nature. If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information.
{% endif %}
<</SYS>>
{{prompt}}[/INST]""",
    "mistral-instruct": (
        "<s>[INST] {{prompt}} [/INST]"
    ),  # The opening <s> tag is not a mistake
    "codellama": """
[INST] {% if system %} {{system}} {% else %} Write code to solve the following coding problem that obeys the constraints and passes the example test cases. Please wrap your code answer using ```: {% endif %}
{{prompt}}
[/INST]
""",
}

model_registry: List[HuggingFaceModel] = []

########### GGUF models ############

quantization = [
    "Q2_K",
    "Q3_K_L",
    "Q3_K_M",
    "Q3_K_S",
    "Q4_0",
    "Q4_K_M",
    "Q4_K_S",
    "Q5_0",
    "Q5_K_M",
    "Q5_K_S",
    "Q6_K",
    "Q8_0",
]

# Llama2-7B
repo_id = "TheBloke/Llama-2-7B-GGUF"

model_registry.extend(
    [
        HuggingFaceModel(
            name="llama2-7b",
            repo_id=repo_id,
            files=[f"llama-2-7b.{quant}.gguf"],
            inference_devices=["cpu", "gpu"],
            quantization=f"GGUF_{quant}",
            runtime="llama.cpp",
        )
        for quant in quantization
    ]
)

# Llama2-7B Chat
repo_id = "TheBloke/Llama-2-7B-Chat-GGUF"

model_registry.extend(
    [
        HuggingFaceModel(
            name="llama2-7b-chat",
            repo_id=repo_id,
            files=[f"llama-2-7b-chat.{quant}.gguf"],
            inference_devices=["cpu", "gpu"],
            quantization=f"GGUF_{quant}",
            runtime="llama.cpp",
            prompt_template_name="llama-2",
            prompt_template_str=prompt_templates["llama-2"],
        )
        for quant in quantization
    ]
)

# Llama2-13B
repo_id = "TheBloke/Llama-2-13B-GGUF"
model_registry.extend(
    [
        HuggingFaceModel(
            name="llama2-13b",
            repo_id=repo_id,
            files=[f"llama-2-13b.{quant}.gguf"],
            inference_devices=["cpu", "gpu"],
            quantization=f"GGUF_{quant}",
            runtime="llama.cpp",
        )
        for quant in quantization
    ]
)

# Llama2-13B Chat
repo_id = "TheBloke/Llama-2-13B-Chat-GGUF"
model_registry.extend(
    [
        HuggingFaceModel(
            name="llama2-13b-chat",
            repo_id=repo_id,
            files=[f"llama-2-13b-chat.{quant}.gguf"],
            inference_devices=["cpu", "gpu"],
            quantization=f"GGUF_{quant}",
            runtime="llama.cpp",
            prompt_template_name="llama-2",
            prompt_template_str=prompt_templates["llama-2"],
        )
        for quant in quantization
    ]
)

# Llama2-70B
repo_id = "TheBloke/Llama-2-70B-GGUF"
model_registry.extend(
    [
        HuggingFaceModel(
            name="llama2-70b",
            repo_id=repo_id,
            files=[f"llama-2-70b.{quant}.gguf"],
            inference_devices=["cpu", "gpu"],
            quantization=f"GGUF_{quant}",
            runtime="llama.cpp",
        )
        for quant in quantization
    ]
)

# Llama2-70B Chat
repo_id = "TheBloke/Llama-2-70B-Chat-GGUF"
model_registry.extend(
    [
        HuggingFaceModel(
            name="llama2-70b-chat",
            repo_id=repo_id,
            files=[f"llama-2-70b-chat.{quant}.gguf"],
            inference_devices=["cpu", "gpu"],
            quantization=f"GGUF_{quant}",
            runtime="llama.cpp",
            prompt_template_name="llama-2",
            prompt_template_str=prompt_templates["llama-2"],
        )
        for quant in quantization
    ]
)

# Mistral-7B-Instruct-v0.2
repo_id = "TheBloke/Mistral-7B-Instruct-v0.2-GGUF"
model_registry.extend(
    [
        HuggingFaceModel(
            name="mistral-7b-instruct-v0.2",
            repo_id=repo_id,
            files=[f"mistral-7b-instruct-v0.2.{quant}.gguf"],
            inference_devices=["cpu", "gpu"],
            quantization=f"GGUF_{quant}",
            runtime="llama.cpp",
            prompt_template_name="mistral-instruct",
            prompt_template_str=prompt_templates["mistral-instruct"],
        )
        for quant in quantization
    ]
)

# Mistral-7B-Instruct-v0.1
repo_id = "TheBloke/Mistral-7B-Instruct-v0.1-GGUF"
model_registry.extend(
    [
        HuggingFaceModel(
            name="mistral-7b-instruct-v0.1",
            repo_id=repo_id,
            files=[f"mistral-7b-instruct-v0.1.{quant}.gguf"],
            inference_devices=["cpu", "gpu"],
            quantization=f"GGUF_{quant}",
            runtime="llama.cpp",
            prompt_template_name="mistral-instruct",
            prompt_template_str=prompt_templates["mistral-instruct"],
        )
        for quant in quantization
    ]
)

# CodeLlama-7B, CodeLlama-34B, CodeLlama-70B
codellama_sizes = ["7b", "34b", "70b"]

for size in codellama_sizes:
    repo_id = f"TheBloke/CodeLlama-{size.capitalize()}-GGUF"
    model_registry.extend(
        [
            HuggingFaceModel(
                name=f"codellama-{size}",
                repo_id=repo_id,
                files=[f"codellama-{size}.{quant}.gguf"],
                inference_devices=["cpu", "gpu"],
                quantization=f"GGUF_{quant}",
                runtime="llama.cpp",
            )
            for quant in quantization
        ]
    )

# CodeLlama-7B-Instruct, CodeLlama-34B-Instruct, CodeLlama-70B-Instruct

for size in codellama_sizes:
    repo_id = f"TheBloke/CodeLlama-{size.capitalize()}-Instruct-GGUF"
    model_registry.extend(
        [
            HuggingFaceModel(
                name=f"codellama-{size}-instruct",
                repo_id=repo_id,
                files=[f"codellama-{size}-instruct.{quant}.gguf"],
                inference_devices=["cpu", "gpu"],
                quantization=f"GGUF_{quant}",
                runtime="llama.cpp",
                prompt_template_name="codellama",
                prompt_template_str=prompt_templates["codellama"],
            )
            for quant in quantization
        ]
    )

# CodeLlama-7B-Python, CodeLlama-34B-Python, CodeLlama-70B-Python

for size in codellama_sizes:
    repo_id = f"TheBloke/CodeLlama-{size.capitalize()}-Python-GGUF"
    model_registry.extend(
        [
            HuggingFaceModel(
                name=f"codellama-{size}-python",
                repo_id=repo_id,
                files=[f"codellama-{size}-python.{quant}.gguf"],
                inference_devices=["cpu", "gpu"],
                quantization=f"GGUF_{quant}",
                runtime="llama.cpp",
                prompt_template_name="codellama",
                prompt_template_str=prompt_templates["codellama"],
            )
            for quant in quantization
        ]
    )


# gte-base
gte_quantization = ["fp16", "fp32"] + quantization
gte_variants = ["base", "small", "large"]

for variant in gte_variants:
    repo_id = f"ChristianAzinn/gte-{variant}-gguf"
    model_registry.extend(
        [
            HuggingFaceModel(
                name=f"gte-{variant}",
                repo_id=repo_id,
                files=[f"gte-{variant}.{quant}.gguf"],
                inference_devices=["cpu", "gpu"],
                quantization=f"GGUF_{quant}",
                runtime="llama.cpp",
            )
            for quant in gte_quantization
        ]
    )


def get_model(name: str, tags: Optional[List[Pair]] = None) -> HuggingFaceModel:
    if tags is None:
        tags = []
    # Add quantization tag if not already present
    if not any(tag[0] == "quantization" for tag in tags):
        tags.append(("quantization", "GGUF_Q4_0"))  # Default quantization

    models = [
        model
        for model in model_registry
        if model.name == name and all(getattr(model.settings, k) == v for k, v in tags)
    ]

    if len(models) > 1:
        raise ValueError(f"Multiple models found with name {name} and tags {tags}")

    if not models:
        raise ValueError(f"Model {name} not found in registry")

    return models[0]

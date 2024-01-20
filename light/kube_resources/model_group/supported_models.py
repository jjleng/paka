from collections import namedtuple

Model = namedtuple("Model", ["name", "url", "sha256"])

SUPPORTED_MODELS = {
    "llama2-7b": Model(
        name="llama2-7b",
        url="https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_0.gguf",
        sha256="9958ee9b670594147b750bbc7d0540b928fa12dcc5dd4c58cc56ed2eb85e371b",
    ),
    "mistral-7b": Model(
        name="mistral-7b",
        url="https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_0.gguf",
        sha256="25d80b918e4432661726ef408b248005bebefe3f8e1ac722d55d0c5dcf2893e0",
    ),
    "codellama-7b": Model(
        name="codellama-7b",
        url="https://huggingface.co/TheBloke/CodeLlama-7B-GGUF/resolve/main/codellama-7b.Q4_0.gguf",
        sha256="33052f6dd41436db2f83bd48017b6fff8ce0184e15a8a227368b4230f1da97b5",
    ),
}

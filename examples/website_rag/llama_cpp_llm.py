from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterator, List, Optional

import requests
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM
from langchain_core.outputs import GenerationChunk
from langchain_core.pydantic_v1 import Field, root_validator
from langchain_core.utils import get_pydantic_field_names
from langchain_core.utils.utils import build_extra_kwargs

logger = logging.getLogger(__name__)


class Client:
    def __init__(self, model_url: str) -> None:
        self.url = model_url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def __call__(self, **kwargs: Any) -> Any:
        if kwargs.get("stream", False):
            with requests.post(
                f"{self.url}/v1/completions",
                headers={**self.headers, "Accept": "text/event-stream"},
                json=kwargs,
                stream=True,
                verify=False,
            ) as response:
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode("utf-8").replace("data: ", "")
                        if line_str.strip() == "[DONE]":
                            return
                        elif line_str.startswith(": ping - "):
                            pass
                        else:
                            json_line = json.loads(line_str)
                            yield json_line
        else:
            response = requests.post(
                f"{self.url}/v1/completions",
                headers=self.headers,
                json=kwargs,
                verify=False,
            )
            return response.json()

    def tokenize(self, text: str) -> int:
        response = requests.post(
            f"{self.url}/v1/embeddings",
            headers=self.headers,
            data={"input": text},
            verify=False,
        )
        return response.json()["usage"]["total_tokens"]


class LlamaCpp(LLM):
    """llama.cpp model."""

    client: Any  #: :meta private:

    model_url: str
    """The url of the model server."""

    suffix: Optional[str] = Field(None)
    """A suffix to append to the generated text. If None, no suffix is appended."""

    max_tokens: Optional[int] = 256
    """The maximum number of tokens to generate."""

    temperature: Optional[float] = 0.8
    """The temperature to use for sampling."""

    top_p: Optional[float] = 0.95
    """The top-p value to use for sampling."""

    logprobs: Optional[int] = Field(None)
    """The number of logprobs to return. If None, no logprobs are returned."""

    echo: Optional[bool] = False
    """Whether to echo the prompt."""

    stop: Optional[List[str]] = []
    """A list of strings to stop generation when encountered."""

    repeat_penalty: Optional[float] = 1.1
    """The penalty to apply to repeated tokens."""

    top_k: Optional[int] = 40
    """The top-k value to use for sampling."""

    last_n_tokens_size: Optional[int] = 64
    """The number of tokens to look back when applying the repeat_penalty."""

    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Any additional parameters to pass to llama_cpp.Llama."""

    streaming: bool = True
    """Whether to stream the results, token by token."""

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        model_url = values["model_url"]

        values["client"] = Client(model_url)

        return values

    @root_validator(pre=True)
    def build_model_kwargs(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Build extra kwargs from additional params that were passed in."""
        all_required_field_names = get_pydantic_field_names(cls)
        extra = values.get("model_kwargs", {})
        values["model_kwargs"] = build_extra_kwargs(
            extra, values, all_required_field_names
        )
        return values

    @property
    def _default_params(self) -> Dict[str, Any]:
        """Get the default parameters for calling llama_cpp."""
        params = {
            "suffix": self.suffix,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "logprobs": self.logprobs,
            "echo": self.echo,
            "stop_sequences": self.stop,  # key here is convention among LLM classes
            "repeat_penalty": self.repeat_penalty,
            "top_k": self.top_k,
        }
        return params

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get the identifying parameters."""
        return self._default_params

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "llamacpp"

    def _get_parameters(self, stop: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Performs sanity check, preparing parameters in format needed by llama_cpp.

        Args:
            stop (Optional[List[str]]): List of stop sequences for llama_cpp.

        Returns:
            Dictionary containing the combined parameters.
        """

        # Raise error if stop sequences are in both input and default params
        if self.stop and stop is not None:
            raise ValueError("`stop` found in both the input and default params.")

        params = self._default_params

        # llama_cpp expects the "stop" key not this, so we remove it:
        params.pop("stop_sequences")

        # then sets it as configured, or default to an empty list:
        params["stop"] = self.stop or stop or []

        return params

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call the Llama model and return the output.

        Args:
            prompt: The prompt to use for generation.
            stop: A list of strings to stop generation when encountered.

        Returns:
            The generated text.

        Example:
            .. code-block:: python

                from langchain_community.llms import LlamaCpp
                llm = LlamaCpp(model_path="/path/to/local/llama/model.bin")
                llm("This is a prompt.")
        """
        if self.streaming:
            # If streaming is enabled, we use the stream
            # method that yields as they are generated
            # and return the combined strings from the first choices's text:
            combined_text_output = ""
            for chunk in self._stream(
                prompt=prompt,
                stop=stop,
                run_manager=run_manager,
                **kwargs,
            ):
                combined_text_output += chunk.text
            return combined_text_output
        else:
            params = self._get_parameters(stop)
            params = {**params, **kwargs}
            result = self.client(prompt=prompt, **params)
            return result["choices"][0]["text"]

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        """Yields results objects as they are generated in real time.

        It also calls the callback manager's on_llm_new_token event with
        similar parameters to the OpenAI LLM class method of the same name.

        Args:
            prompt: The prompts to pass into the model.
            stop: Optional list of stop words to use when generating.

        Returns:
            A generator representing the stream of tokens being generated.

        Yields:
            A dictionary like objects containing a string token and metadata.
            See llama-cpp-python docs and below for more.

        Example:
            .. code-block:: python

                from langchain_community.llms import LlamaCpp
                llm = LlamaCpp(
                    model_path="/path/to/local/model.bin",
                    temperature = 0.5
                )
                for chunk in llm.stream("Ask 'Hi, how are you?' like a pirate:'",
                        stop=["'","\n"]):
                    result = chunk["choices"][0]
                    print(result["text"], end='', flush=True)

        """
        params = {**self._get_parameters(stop), **kwargs}
        result = self.client(prompt=prompt, stream=True, **params)
        for part in result:
            logprobs = part["choices"][0].get("logprobs", None)
            chunk = GenerationChunk(
                text=part["choices"][0]["text"],
                generation_info={"logprobs": logprobs},
            )
            yield chunk
            if run_manager:
                run_manager.on_llm_new_token(
                    token=chunk.text, verbose=True, log_probs=logprobs
                )

    def get_num_tokens(self, text: str) -> int:
        return self.client.tokenize(text)

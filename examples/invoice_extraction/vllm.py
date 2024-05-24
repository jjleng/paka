# Adapter for using the vLLM model from the LangChain API.
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
from sseclient import SSEClient

logger = logging.getLogger(__name__)


class Client:
    def __init__(self, model_url: str) -> None:
        self.url = model_url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def invoke(self, **kwargs: Any) -> Any:
        response = requests.post(
            f"{self.url}/v1/completions",
            headers=self.headers,
            json=kwargs,
            verify=False,
        )
        print(response.text)
        return response.json()

    def stream(self, **kwargs: Any) -> Any:
        with requests.post(
            f"{self.url}/v1/completions",
            headers={**self.headers, "Accept": "text/event-stream"},
            json=kwargs,
            stream=True,
            verify=False,
        ) as response:
            client = SSEClient((chunk for chunk in response.iter_content()))
            for event in client.events():
                if not event.event == "message":
                    continue
                if event.data.strip() == "[DONE]":
                    break
                else:
                    json_line = json.loads(event.data)
                    yield json_line

    def tokenize(self, text: str) -> int:
        response = requests.post(
            f"{self.url}/v1/embeddings",
            headers=self.headers,
            json={"input": text},
            verify=False,
        )
        return response.json()["usage"]["prompt_tokens"]


class Vllm(LLM):
    """Vllm model."""

    client: Any = None  #: :meta private:

    model: str
    """The model name."""

    model_url: str
    """The url of the model server."""

    suffix: Optional[str] = None
    """A suffix to append to the generated text. If None, no suffix is appended."""

    max_tokens: Optional[int] = 256
    """The maximum number of tokens to generate."""

    temperature: Optional[float] = 0.8
    """The temperature to use for sampling."""

    top_p: Optional[float] = 0.95
    """The top-p value to use for sampling."""

    logprobs: Optional[int] = None
    """The number of logprobs to return. If None, no logprobs are returned."""

    echo: Optional[bool] = False
    """Whether to echo the prompt."""

    stop: Optional[List[str]] = []
    """A list of strings to stop generation when encountered."""

    top_k: Optional[int] = 40
    """The top-k value to use for sampling."""

    last_n_tokens_size: Optional[int] = 64
    """The number of tokens to look back when applying the repeat_penalty."""

    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Any additional parameters."""

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
        """Get the default parameters."""
        params = {
            "model": self.model,
            "suffix": self.suffix,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "logprobs": self.logprobs,
            "echo": self.echo,
            "stop": self.stop,  # key here is convention among LLM classes
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
        return "openai"

    def _get_parameters(self, stop: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Performs sanity check.

        Args:
            stop (Optional[List[str]]): List of stop sequences.

        Returns:
            Dictionary containing the combined parameters.
        """

        # Raise error if stop sequences are in both input and default params
        if self.stop and stop is not None:
            raise ValueError("`stop` found in both the input and default params.")

        params = self._default_params

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
            result = self.client.invoke(prompt=prompt, stream=False, **params)
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
        """
        params = {**self._get_parameters(stop), **kwargs}
        result = self.client.stream(prompt=prompt, stream=True, **params)
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

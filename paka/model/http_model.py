from __future__ import annotations

import concurrent.futures
from typing import List, Optional

import requests

from paka.model.base_model import BaseMLModel
from paka.model.store import ModelStore


class HttpSourceModel(BaseMLModel):
    def __init__(
        self,
        name: str,
        urls: List[str],
        model_store: ModelStore,
        quantization: Optional[str] = None,
        prompt_template_name: Optional[str] = None,
        prompt_template_str: Optional[str] = None,
    ) -> None:
        super().__init__(
            name=name,
            model_store=model_store,
            quantization=quantization,
            prompt_template_name=prompt_template_name,
            prompt_template_str=prompt_template_str,
        )
        self.urls = urls

    def save(self) -> None:
        """
        Save the model to a model store.
        """
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.concurrency
        ) as executor:
            futures = [executor.submit(self._save_single_url, url) for url in self.urls]
            concurrent.futures.wait(futures)
            self.finish()

    def _save_single_url(self, url: str) -> None:
        with requests.get(url, stream=True) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            fname = url.split("/")[-1]
            self.save_single_stream(f"{self.name}/{fname}", response, total_size)

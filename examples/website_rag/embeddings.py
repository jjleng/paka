import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

import requests
from constants import LLM_URL
from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseModel
from requests.exceptions import RequestException

MAX_ATTEMPTS = 10000

"""
This is the more efficient way to embed documents and queries. But it requires more memory.
class LlamaEmbeddings(BaseModel, Embeddings):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        url = "http://llama2-7b/v1/embeddings"
        headers = {"Content-Type": "application/json", "accept": "application/json"}
        data = {
            "input": texts,
        }

        response = requests.post(url, headers=headers, json=data, verify=False)

        return [data["embedding"] for data in response.json()["data"]]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]
"""


class LlamaEmbeddings(BaseModel, Embeddings):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""
        # This is less efficient than the commented out code above
        # However, this is to avoid memory exhaustion for the CPU environment
        with ThreadPoolExecutor() as executor:
            return list(executor.map(self.embed_query, texts))

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        url = f"{LLM_URL}/v1/embeddings"
        headers = {"Content-Type": "application/json", "accept": "application/json"}
        data = {
            "input": [text],
        }

        max_attempts = MAX_ATTEMPTS
        for attempt in range(max_attempts):
            try:
                # No timeout is set here
                response = requests.post(url, headers=headers, json=data, verify=False)
                response.raise_for_status()
                return [data["embedding"] for data in response.json()["data"]][0]
            except RequestException:
                if attempt < max_attempts - 1:
                    time.sleep(1)
                    continue
                else:
                    raise
        raise Exception("Failed to embed query")

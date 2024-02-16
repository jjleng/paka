import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

import requests
from constants import EMBEDDING_URL
from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseModel
from requests.exceptions import RequestException

MAX_ATTEMPTS = 10000


class LlamaEmbeddings(BaseModel, Embeddings):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        url = f"{EMBEDDING_URL}/v1/embeddings"
        headers = {"Content-Type": "application/json", "accept": "application/json"}
        data = {
            "input": texts,
        }

        response = requests.post(url, headers=headers, json=data, verify=False)

        return [data["embedding"] for data in response.json()["data"]]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

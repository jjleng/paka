from typing import List

import requests
from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseModel


class LlamaEmbeddings(BaseModel, Embeddings):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""
        url = "http://llama2-7b/v1/embeddings"
        headers = {"Content-Type": "application/json", "accept": "application/json"}
        data = {
            "input": texts,
        }

        response = requests.post(url, headers=headers, json=data, verify=False)

        return [data["embedding"] for data in response.json()["data"]]

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        return self.embed_documents([text])[0]

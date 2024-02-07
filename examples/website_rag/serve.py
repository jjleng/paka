import os

from embeddings import LlamaEmbeddings
from fastapi import FastAPI
from langchain_community.vectorstores import Qdrant
from langserve import add_routes
from qdrant_client import QdrantClient

port = int(os.getenv("PORT", 8080))

client = QdrantClient(
    url="http://qdrant.qdrant.svc.cluster.local",
    prefer_grpc=True,
)
collection_name = "langchain_documents"

embeddings = LlamaEmbeddings()
qdrant = Qdrant(client, collection_name, embeddings=embeddings)

retriever = qdrant.as_retriever()

app = FastAPI(
    title="LangChain Docs Server",
    version="0.1.0",
    description="Spin up a simple api server to retrieve documents from the vector store.",
)
# Adds routes to the app for using the retriever under:
# /invoke
# /batch
# /stream
add_routes(app, retriever)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=port)

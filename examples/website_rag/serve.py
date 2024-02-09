import os
from typing import Annotated, Any

from constants import QDRANT_URL
from embeddings import LlamaEmbeddings
from fastapi import Depends, FastAPI, Request, Response
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Qdrant
from langchain_core.runnables import RunnableLambda
from langserve import APIHandler, add_routes
from llama_cpp_llm import LlamaCpp
from qdrant_client import QdrantClient

port = int(os.getenv("PORT", 8080))

client = QdrantClient(
    url=QDRANT_URL,
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


def run_llm(query: str) -> Any:
    llm = LlamaCpp(
        model_url="http://llama2-7b.52.38.72.240.sslip.io",
        temperature=0,
    )

    qa = RetrievalQA.from_chain_type(
        llm=llm, retriever=retriever, chain_type="stuff", return_source_documents=True
    )

    return qa.invoke({"query": query})


async def _get_api_handler() -> APIHandler:
    """Prepare a RunnableLambda."""
    return APIHandler(RunnableLambda(run_llm), path="/v2")


@app.post("/v2/invoke")
async def v2_invoke(
    request: Request, runnable: Annotated[APIHandler, Depends(_get_api_handler)]
) -> Response:
    """Handle invoke request."""
    # The API Handler validates the parts of the request
    # that are used by the runnnable (e.g., input, config fields)
    return await runnable(request)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=port)

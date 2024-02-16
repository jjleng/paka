import logging
import os
import time
from typing import Annotated, Any

from constants import LLM_URL, QDRANT_URL
from embeddings import LlamaEmbeddings
from fastapi import Depends, FastAPI, Request, Response
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Qdrant
from langchain_core.runnables import RunnableLambda
from langserve import APIHandler, add_routes
from llama_cpp_llm import LlamaCpp
from qdrant_client import QdrantClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

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
    start_time = time.time()
    logging.info(f"Running LLM with query: {query}")
    llm = LlamaCpp(
        model_url=LLM_URL,
        temperature=0,
        max_tokens=2500,
        streaming=False,
    )

    qa = RetrievalQA.from_chain_type(
        llm=llm, retriever=retriever, chain_type="stuff", return_source_documents=True
    )

    result = qa.invoke({"query": query})
    logging.info(f"LLM result: {result}")

    end_time = time.time()
    logging.info(f"Execution time: {end_time - start_time} seconds")
    return result


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
    return await runnable.invoke(request)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=port)

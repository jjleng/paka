import logging
import os
import shutil
import time
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile
from langchain.callbacks.base import BaseCallbackHandler
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.prompts import PromptTemplate
from llama_cpp_llm import LlamaCpp
from output_parser import invoice_parser

LLM_URL = "http://llama2-7b-chat"

port = int(os.getenv("PORT", 8080))
app = FastAPI(
    title="Invoice Extraction Server",
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)


class CustomHandler(BaseCallbackHandler):
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> Any:
        formatted_prompts = "\n".join(prompts)
        logging.info(f"Prompt:\n{formatted_prompts}")


def extract(pdf_path: str) -> str:
    pdf_loader = PyPDFLoader(pdf_path)
    pages = pdf_loader.load_and_split()
    page_content = pages[0].page_content

    logging.info(f"Extracting from PDF: {pdf_path}")

    template = """
     Extract all the following values : invoice number, invoice date, remit to company, remit to address,
     tax ID, invoice to customer, invoice to address, total amount from this invoice: {invoice_text}

     {format_instructions}

     Only returns the extracted JSON object, don't say anything else.
    """

    # Future paka code will be able to handle this
    chat_template = f"[INST] <<SYS>><</SYS>>\n\n{template} [/INST]\n"

    prompt = PromptTemplate(
        template=chat_template,
        input_variables=["invoice_text"],
        partial_variables={
            "format_instructions": invoice_parser.get_format_instructions()
        },
    )

    llm = LlamaCpp(
        model_url=LLM_URL,
        temperature=0,
        streaming=False,
    )

    chain = prompt | llm | invoice_parser

    start_time = time.time()
    result = chain.invoke(
        {"invoice_text": page_content}, config={"callbacks": [CustomHandler()]}
    )
    end_time = time.time()
    logging.info(f"Execution time: {end_time - start_time} seconds")
    return result.to_dict()


@app.post("/extract_invoice")
async def upload_file(file: UploadFile = File(...)) -> Any:
    unique_filename = str(uuid4())
    tmp_file_path = f"/tmp/{unique_filename}"

    try:
        with open(tmp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return extract(tmp_file_path)
    finally:
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=port)

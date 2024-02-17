import sys
from typing import Generator

from bs4.element import Tag
from constants import QDRANT_URL
from crawler import crawl
from embeddings import LlamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Qdrant
from langchain_core.documents import Document


def _metadata_extractor(raw_html: str, url: str) -> dict:
    """Extract metadata from raw html using BeautifulSoup."""
    metadata = {"source": url}

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print(
            "The bs4 package is required for default metadata extraction. "
            "Please install it with `pip install bs4`."
        )
        return metadata
    soup = BeautifulSoup(raw_html, "html.parser")
    if title := soup.find("title"):
        metadata["title"] = title.get_text()
    if (description := soup.find("meta", attrs={"name": "description"})) and isinstance(
        description, Tag
    ):
        description_content = description.get("content", "") or ""
        metadata["description"] = (
            " ".join(description_content)
            if isinstance(description_content, list)
            else description_content
        )
    else:
        metadata["description"] = ""
    if (html := soup.find("html")) and isinstance(html, Tag):
        html_lang = html.get("lang", "") or ""
        metadata["language"] = (
            " ".join(html_lang) if isinstance(html_lang, list) else html_lang
        )
    else:
        metadata["language"] = ""
    return metadata


def docs_loader(website: str) -> Generator[Document, None, None]:
    # We use a custom crawler. LangChain's RecursiveUrlLoader cannot be used as is.
    crawler = crawl(website, max_depth=0)

    for url, html_content in crawler:
        yield Document(
            page_content=html_content, metadata=_metadata_extractor(html_content, url)
        )


def embed_website(website: str) -> None:
    chunk_size = 400
    chunk_overlap = 50
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    docs = text_splitter.split_documents(docs_loader(website))
    embeddings = LlamaEmbeddings()

    print("Embedding documents...")
    print("Total number of documents:", len(docs))

    Qdrant.from_documents(
        docs,
        embeddings,
        url=QDRANT_URL,
        prefer_grpc=True,
        collection_name="langchain_documents",
    )
    print("done")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        embed_website(sys.argv[1])
    else:
        print("Please provide a URL as a command-line argument.")

from typing import Generator

from crawler import crawl
from langchain.text_splitter import RecursiveCharacterTextSplitter
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
    if description := soup.find("meta", attrs={"name": "description"}):
        metadata["description"] = description.get("content", None)
    if html := soup.find("html"):
        metadata["language"] = html.get("lang", None)
    return metadata


def docs_loader(website: str) -> Generator[Document, None, None]:
    # We use a custom crawler. LangChain's RecursiveUrlLoader cannot be used as is.
    crawler = crawl(website, max_depth=5)

    for url, html_content in crawler:
        yield Document(
            page_content=html_content, metadata=_metadata_extractor(html_content, url)
        )


def embedding(website: str) -> None:
    chunk_size = 300
    chunk_overlap = 50
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    docs = text_splitter.split_documents(docs_loader(website))
    print(len(docs))


embedding("https://python.langchain.com/docs/get_started/introduction")

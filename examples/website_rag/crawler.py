import os
from typing import Generator, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def is_relative_url(url: str) -> bool:
    return not bool(urlparse(url).netloc)


def get_root_url(url: str) -> str:
    parsed_url = urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}"


def get_filename(save_dir: str, href: str) -> str:
    parsed_url = urlparse(href)
    path = parsed_url.path
    if path.endswith("/") or not path:
        path = path + "index.html"
    else:
        if not path.endswith(".html"):
            path = path + ".html"
    filename = os.path.join(save_dir, parsed_url.netloc, path.lstrip("/"))
    return filename


def save_html_file(response_text: str, url: str, save_dir: str) -> None:
    filename = get_filename(save_dir, url)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as file:
        file.write(response_text)


def get_html(url: str) -> str:
    try:
        response = requests.get(url)
        content_type = response.headers["content-type"]
        if "html" in content_type:
            return response.text
    except Exception as e:
        print(f"Failed to get {url}: {e}")
    return ""


def crawl(url: str, max_depth: int = 3) -> Generator[Tuple[str, str], None, None]:
    visited = set()

    def _crawl(url: str, depth: int = 0) -> Generator[Tuple[str, str], None, None]:
        url_without_fragment = url.split("#")[0]

        if (
            depth > max_depth
            or not url.startswith("https")
            or not url.startswith("http")
        ):
            return

        root_url = get_root_url(url)

        orig_html_content = get_html(url)
        soup = BeautifulSoup(orig_html_content, "html.parser")

        yield url, soup.get_text(separator=" ", strip=True)

        visited.add(url_without_fragment)

        for link in soup.find_all("a"):
            href = link.get("href")
            if not href:
                continue
            href_domain = urlparse(href).netloc
            url_domain = urlparse(url).netloc
            if href_domain and href_domain != url_domain:
                continue

            full_url = urljoin(root_url, href) if is_relative_url(href) else href
            if full_url not in visited:
                yield from _crawl(full_url, depth + 1)

    yield from _crawl(url)

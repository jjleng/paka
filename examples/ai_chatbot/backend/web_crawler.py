# Standard Library Imports
import logging
import os
import re
from collections import deque
from typing import List
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv

# Third-Party Imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.wait import WebDriverWait

# Local Application/Module Specific Imports
load_dotenv(".env")

logger = logging.getLogger(__name__)
handler = logging.FileHandler("logging/web_crawler.log")
handler.setFormatter(logging.Formatter(os.getenv("LOGGING_FORMAT")))
logger.addHandler(handler)


def validate_url(url: str) -> bool:
    HTTP_URL_PATTERN = (
        r"^(?:http|ftp)s?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$"
    )
    patterns = re.compile(HTTP_URL_PATTERN, re.IGNORECASE)

    return re.match(patterns, url) is not None


def get_domain_hyperlinks(
    links: List[str], local_domain: str, folder_path: List[str]
) -> List[str]:

    clean_links = set()
    for link in set(links):

        clean_link = None

        if validate_url(link):

            parsed_url = urlparse(link)
            if parsed_url.netloc == local_domain and any(
                parsed_url.path.startswith(path) for path in folder_path
            ):
                clean_link = urlunparse(parsed_url._replace(fragment=""))

        else:
            if link.startswith("/"):
                link = link[1:]
            elif link.startswith("#") or link.startswith("mailto:"):
                continue
            clean_link = "https://" + local_domain + "/" + link

        if clean_link is not None:
            if clean_link.endswith("/"):
                clean_link = clean_link[:-1]
            clean_links.add(clean_link)

    return list(clean_links)


def crawl(url: str, folder_name: str = "site_content", local_domain: str = "") -> None:

    if not validate_url(url):
        return None

    if local_domain == "":
        local_domain = urlparse(url).netloc

    if not os.path.exists(f"{folder_name}/"):
        os.mkdir(f"{folder_name}/")

    if not os.path.exists(f"{folder_name}/{local_domain}"):
        os.mkdir(f"{folder_name}/{local_domain}")

    # chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--no-sandbox")
    # chrome_options.add_argument("--disable-dev-shm-usage")

    queue = deque([url])
    seen = set([url])
    count = 0
    while queue:
        count += 1

        url = queue.pop()
        logger.debug(f"Parsing HTML content from {url}.")

        links = []
        try:
            # driver = webdriver.Chrome(options=chrome_options)
            driver = webdriver.Chrome()
            driver.get(url)
            wait = WebDriverWait(driver, timeout=3)

            try:
                # wait.until(EC.visibility_of_element_located((By.CLASS_NAME, "Box-sc-g0xbh4-0 ehcSsh")))
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                has_article = True
            except:
                has_article = False

            html_content = driver.page_source
            links = [
                element.get_attribute("href")
                for element in driver.find_elements(By.CSS_SELECTOR, "a[href]")
            ]

        finally:
            driver.delete_all_cookies()
            driver.quit()

        if has_article:
            with open(
                f'{folder_name}/{local_domain}/{local_domain+urlparse(url).path.replace("/", "_")}.txt',
                "w",
                encoding="UTF-8",
            ) as f:
                f.write(url + "\n")
                f.write(html_content)

        folder_path = [urlparse(url).path]
        for link in get_domain_hyperlinks(links, local_domain, folder_path):
            if link not in seen:
                queue.append(link)
                seen.add(link)

    logger.debug(f"Total number of web pages crawled: {count}.")

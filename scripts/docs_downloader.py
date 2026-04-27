import os

from pathlib import Path
from urllib.parse import urljoin

import bs4
from bs4 import BeautifulSoup
from rich import print

from selenium import webdriver
from selenium.webdriver.common.webdriver import LocalWebDriver
from selenium.webdriver.common.by import By

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless=new")  # for Chrome >= 109
driver: LocalWebDriver = webdriver.Chrome(options=chrome_options)

base_url = "https://happinessmp.net/"
OUTPUT_DIR = Path(os.curdir).absolute()
OUTPUT_DIR.mkdir(exist_ok=True)
docs_front_page = "docs/server/getting-started"


def download_front_page(url: str):
    filepath = OUTPUT_DIR / (url + ".html")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    href = urljoin(base_url, url)

    print(f"[bold green] Fetching {href}")
    print("will be saved to:", filepath)
    driver.get(href)

    elem = driver.find_element(By.CLASS_NAME, "menu__link--sublist")
    elem.click()

    with filepath.open("w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"[green] {filepath} saved.")


# download_front_page(docs_front_page)

with open(docs_front_page + ".html", encoding="utf8") as reader:
    soup = BeautifulSoup(reader.read(), "html.parser")


def download_and_save(rel_url: str):
    rel_url = rel_url.removeprefix("/")

    filepath = OUTPUT_DIR.joinpath((rel_url + ".html"))
    filepath.parent.mkdir(parents=True, exist_ok=True)

    href = urljoin(base_url, rel_url)
    print(f"[bold green] Fetching {href}")
    driver.get(href)

    print("will be saved to:", filepath)
    with filepath.open("w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"[green] {filepath} saved.")


def get_links(soup: BeautifulSoup, category_name: str) -> set[str]:
    links: set[str] = set()

    category_span = soup.find(
        name="span",
        attrs={"title": category_name, "class": ["categoryLinkLabel_W154"]},
    )

    if category_span is None:
        print(f"[bold red] Category {category_name} not found")
        return links

    a_tag = category_span.parent
    assert a_tag is not None

    div_tag = a_tag.parent
    assert div_tag is not None

    ul_tag = div_tag.find_next_sibling("ul")
    assert ul_tag is not None

    for item in ul_tag:
        # print(item)
        if isinstance(item, bs4.NavigableString):
            continue
        a = item.find_next("a")
        if a is None:
            print(f"[bold red] Link not found for item {item}")
            continue

        link = a.attrs["href"]
        assert isinstance(link, str)
        links.add(link)

    return links


def download_category(soup: BeautifulSoup, category_name: str):
    links = get_links(soup, category_name)
    print(f"Found {len(links)} links to download")

    for link in links:
        if link == "#":
            continue
        download_and_save(link)


download_and_save("docs/scripting/events")


driver.quit()

"""Download apartment-for-sale listings from Sprzedajemy.pl.

Usage:
    uv run python -m scraper.download_offers --city krakow --limit 120
"""

import argparse
import random
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

BASE_URL = "https://sprzedajemy.pl"
PAGE_SIZE = 30
RAW_HTML_DIR = Path("data/raw/html")

OFFER_ID_PATTERN = re.compile(r"-nr(\d+)$")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}


def search_url(city: str, offset: int) -> str:
    return f"{BASE_URL}/{city}/nieruchomosci/mieszkania/sprzedaz?offset={offset}"


def offer_id_from_url(url: str) -> str | None:
    match = OFFER_ID_PATTERN.search(url)
    return match.group(1) if match else None


def find_offer_links(html: str) -> list[str]:
    """Return unique listing URLs from a search results page, preserving display order."""
    links: list[str] = []
    for a in HTMLParser(html).css("a[href]"):
        href = (a.attributes.get("href") or "").split("?")[0]
        if offer_id_from_url(href):
            full = urljoin(BASE_URL, href)
            if full not in links:
                links.append(full)
    return links


def polite_pause() -> None:
    """Wait for a random interval between requests to avoid overloading the website."""
    time.sleep(random.uniform(1.5, 3.0))


def collect_offer_links(client: httpx.Client, city: str, limit: int) -> list[str]:
    links: list[str] = []
    offset = 0
    while len(links) < limit:
        url = search_url(city, offset)
        print(f"[lista] {url}")
        response = client.get(url)
        response.raise_for_status()
        page_links = find_offer_links(response.text)
        new_links = [link for link in page_links if link not in links]
        if not new_links:
            break
        links.extend(new_links)
        offset += PAGE_SIZE
        polite_pause()
    return links[:limit]


def download_offer(client: httpx.Client, url: str) -> bool:
    """Save listing HTML. Return False if the file is cached or the request fails."""
    offer_id = offer_id_from_url(url)
    path = RAW_HTML_DIR / f"{offer_id}.html"
    if path.exists():
        return False
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as error:
        print(f"  ! error while fetching {url}: {error}")
        return False
    path.write_text(response.text, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download apartment-for-sale listings from Sprzedajemy.pl"
    )
    parser.add_argument("--city", default="krakow", help="city slug from the URL, e.g., krakow")
    parser.add_argument("--limit", type=int, default=120, help="number of listings to download")
    args = parser.parse_args()

    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20) as client:
        links = collect_offer_links(client, args.city, args.limit)
        print(f"\nFound {len(links)} listings, downloading details...")
        downloaded = 0
        for i, url in enumerate(links, start=1):
            if download_offer(client, url):
                downloaded += 1
                print(f"  [{i}/{len(links)}] saved {offer_id_from_url(url)}")
                polite_pause()
            else:
                print(f"  [{i}/{len(links)}] skipped {offer_id_from_url(url)}")
    print(f"\nDone: {downloaded} new files, directory {RAW_HTML_DIR}")


if __name__ == "__main__":
    main()

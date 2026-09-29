"""Extraction: raw listing HTML -> raw JSON record (not normalized yet).

Run: uv run python -m etl.extract
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from selectolax.parser import HTMLParser

RAW_HTML_DIR = Path("data/raw/html")
OUTPUT_FILE = Path("data/raw/offers.jsonl")
SOURCE = "sprzedajemy"


def find_product_ld(tree: HTMLParser) -> dict[str, Any] | None:
    """Returns the JSON-LD Product block (offer data) or None."""
    for script in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.text())
        except json.JSONDecodeError:
            continue
        types = data.get("@type", [])
        if "Product" in (types if isinstance(types, list) else [types]):
            return data
    return None


def extract_attributes(tree: HTMLParser) -> dict[str, str]:
    """
    Returns the list of offer parameters as a dictionary {label: value},
    e.g., {"Area": "51 m²"}.
    """
    attributes: dict[str, str] = {}
    for item in tree.css("ul.attribute-list li.item"):
        label, value = item.css_first("span"), item.css_first("strong")
        if label and value:
            attributes[label.text(strip=True)] = value.text(strip=True)
    return attributes


def meta_content(tree: HTMLParser, prop: str) -> str | None:
    node = tree.css_first(f'meta[property="{prop}"]')
    return node.attributes.get("content") if node else None


def split_address(address: str | None, fallback_city: str | None) -> tuple[str | None, str | None]:
    """E.g., "Kraków, Nowa Huta" -> ("Kraków", "Nowa Huta"). If no address: city from meta tag."""
    if not address:
        return fallback_city, None
    parts = [part.strip() for part in address.split(",") if part.strip()]
    city = parts[0] if parts else fallback_city
    district = parts[1] if len(parts) > 1 else None
    return city, district


def extract_offer(path: Path) -> dict[str, Any] | None:
    tree = HTMLParser(path.read_text(encoding="utf-8"))
    product = find_product_ld(tree)
    if product is None:
        return None

    offers = product.get("offers", {})
    address = product.get("owns", {}).get("address")
    city, district = split_address(address, meta_content(tree, "og:locality"))
    images = product.get("image") or []

    return {
        "source": SOURCE,
        "source_id": path.stem,
        "url": meta_content(tree, "og:url"),
        "fetched_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
        "title": product.get("name"),
        "description": product.get("description"),
        "price": offers.get("price"),
        "currency": offers.get("priceCurrency"),
        "item_condition": offers.get("itemCondition"),
        "address_raw": address,
        "city": city,
        "district": district,
        "images": images if isinstance(images, list) else [images],
        "attributes": extract_attributes(tree),
    }


def main() -> None:
    files = sorted(RAW_HTML_DIR.glob("*.html"))
    records, skipped = [], []
    for path in files:
        record = extract_offer(path)
        if record is None:
            skipped.append(path.name)
        else:
            records.append(record)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    without_district = sum(1 for record in records if not record["district"])
    print(f"Saved {len(records)} records to {OUTPUT_FILE}")
    print(f"Skipped (missing JSON-LD): {len(skipped)} {skipped}")
    print(f"Without district: {without_district}")


if __name__ == "__main__":
    main()

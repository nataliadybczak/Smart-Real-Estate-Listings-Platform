"""Quality check of downloaded HTML files - whether all have the expected structure.

Run: uv run python -m etl.check_raw
"""

from collections import Counter
from pathlib import Path

from selectolax.parser import HTMLParser

from etl.extract import find_product_ld

RAW_HTML_DIR = Path("data/raw/html")


def main() -> None:
    files = sorted(RAW_HTML_DIR.glob("*.html"))
    print(f"Files: {len(files)}\n")

    attribute_labels: Counter[str] = Counter()
    cities: Counter[str] = Counter()
    problems: list[str] = []

    for path in files:
        tree = HTMLParser(path.read_text(encoding="utf-8"))
        product = find_product_ld(tree)
        if product is None:
            problems.append(f"{path.name}: missing JSON-LD Product")
            continue
        if not product.get("offers", {}).get("price"):
            problems.append(f"{path.name}: missing price")
        if not product.get("description"):
            problems.append(f"{path.name}: missing description")
        address = product.get("owns", {}).get("address") or "(no address)"
        cities[address.split(",")[0].strip()] += 1

        labels = [span.text(strip=True) for span in tree.css("ul.attribute-list li.item span")]
        if not labels:
            problems.append(f"{path.name}: missing parameter list")
        attribute_labels.update(labels)

    print("How often each parameter occurs:")
    for label, count in attribute_labels.most_common():
        print(f"  {label:<25} {count:>4} / {len(files)}")

    print("\nCities:")
    for city, count in cities.most_common():
        print(f"  {city:<25} {count:>4}")

    print(f"\nProblems ({len(problems)}):")
    for problem in problems:
        print("  " + problem)


if __name__ == "__main__":
    main()

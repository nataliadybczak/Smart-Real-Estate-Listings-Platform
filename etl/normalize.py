"""Normalization: raw record (text from the page) -> clean, typed listing record.

Rules:
- Suspicious values are are flagged,
- Records that are not apartment listings are rejected with a reason,
- Rare parameters go into extra_attributes instead of separate, empty columns.

Run: uv run python -m etl.normalize
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from etl.dedup import mark_duplicates
from etl.districts import match_district

INPUT_FILE = Path("data/raw/offers.jsonl")
OUTPUT_FILE = Path("data/processed/listings.jsonl")

MIN_PRICE_PER_M2 = 5_000
MAX_PRICE_PER_M2 = 40_000
MIN_M2_PER_ROOM = 8


MAPPED_ATTRIBUTES = {
    "Oferta od",
    "Rynek",
    "Cena za m²",
    "Powierzchnia",
    "Liczba pokoi",
    "Piętro",
    "Rok budowy",
    "Zabudowa",
    "Forma własności",
}

MARKETS = {"pierwotny": "primary", "wtórny": "secondary"}
SELLER_TYPES = {"firmy": "agency", "osoby prywatnej": "private"}
NOT_AN_APARTMENT = re.compile(r"\bdom(y|ek)?\b", re.IGNORECASE)

Market = Literal["primary", "secondary"]
SellerType = Literal["agency", "private"]


class NormalizedListing(BaseModel):
    source: str
    source_id: str
    url: str | None
    fetched_at: str
    title: str
    description: str
    price_pln: int
    area_m2: float
    price_per_m2: int
    rooms: int | None
    floor: int | None
    build_year: int | None
    market: Market | None
    seller_type: SellerType | None
    building_type: str | None
    ownership: str | None
    city: str | None
    district: str | None
    location_raw: str | None
    images: list[str]
    extra_attributes: dict[str, str]
    flags: list[str]
    duplicate_of: str | None = None


class RejectedRecord(BaseModel):
    source_id: str
    reason: str


def parse_number(text: str | None) -> float | None:
    if not text:
        return None
    compact = re.sub(r"\s", "", text).replace(",", ".")
    match = re.search(r"\d+(\.\d+)?", compact)
    return float(match.group()) if match else None


def parse_int(text: str | None) -> int | None:
    number = parse_number(text)
    return int(number) if number is not None else None


def parse_floor(text: str | None) -> int | None:
    if not text:
        return None
    lowered = text.strip().lower()
    if lowered == "parter":
        return 0
    if lowered == "suterena":
        return -1
    return parse_int(lowered)


def quality_flags(
    *, area_m2: float, price_per_m2: int, rooms: int | None, ownership: str | None, title: str
) -> list[str]:
    flags = []
    if not MIN_PRICE_PER_M2 <= price_per_m2 <= MAX_PRICE_PER_M2:
        flags.append("price_per_m2_out_of_range")
    if rooms and area_m2 / rooms < MIN_M2_PER_ROOM:
        flags.append("rooms_implausible")
    if ownership == "udział" or "udział" in title.lower():
        flags.append("share_not_whole_flat")
    return flags


def normalize_record(raw: dict[str, Any]) -> NormalizedListing | RejectedRecord:
    source_id = raw["source_id"]
    attributes: dict[str, str] = raw.get("attributes", {})

    if raw.get("currency") != "PLN":
        return RejectedRecord(source_id=source_id, reason="currency_not_pln")
    if NOT_AN_APARTMENT.search(raw.get("title") or ""):
        return RejectedRecord(source_id=source_id, reason="not_an_apartment")

    price = parse_number(raw.get("price"))
    area = parse_number(attributes.get("Powierzchnia"))
    if not price or not area:
        return RejectedRecord(source_id=source_id, reason="missing_price_or_area")

    price_pln, area_m2 = round(price), round(area, 2)
    price_per_m2 = round(price_pln / area_m2)
    rooms = parse_int(attributes.get("Liczba pokoi"))
    ownership = attributes.get("Forma własności")
    location_raw = raw.get("district")

    return NormalizedListing(
        source=raw["source"],
        source_id=source_id,
        url=raw.get("url"),
        fetched_at=raw["fetched_at"],
        title=raw["title"].strip(),
        description=raw.get("description") or "",
        price_pln=price_pln,
        area_m2=area_m2,
        price_per_m2=price_per_m2,
        rooms=rooms,
        floor=parse_floor(attributes.get("Piętro")),
        build_year=parse_int(attributes.get("Rok budowy")),
        market=MARKETS.get(attributes.get("Rynek", "")),
        seller_type=SELLER_TYPES.get(attributes.get("Oferta od", "")),
        building_type=attributes.get("Zabudowa"),
        ownership=ownership,
        city=raw.get("city"),
        district=match_district(location_raw),
        location_raw=location_raw,
        images=raw.get("images", []),
        extra_attributes={k: v for k, v in attributes.items() if k not in MAPPED_ATTRIBUTES},
        flags=quality_flags(
            area_m2=area_m2,
            price_per_m2=price_per_m2,
            rooms=rooms,
            ownership=ownership,
            title=raw["title"],
        ),
    )


def main() -> None:
    raw_records = [json.loads(line) for line in INPUT_FILE.read_text(encoding="utf-8").splitlines()]
    results = [normalize_record(raw) for raw in raw_records]
    listings = [r for r in results if isinstance(r, NormalizedListing)]
    rejected = [r for r in results if isinstance(r, RejectedRecord)]
    mark_duplicates(listings)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        for listing in listings:
            file.write(listing.model_dump_json() + "\n")

    duplicates = [item for item in listings if item.duplicate_of]
    print(f"Input: {len(raw_records)} | Normalized: {len(listings)} | Rejected: {len(rejected)}")
    for record in rejected:
        print(f"  rejected {record.source_id}: {record.reason}")
    print("Flags:", dict(Counter(flag for item in listings for flag in item.flags)))
    print(f"Duplicates: {len(duplicates)}")
    for item in duplicates:
        print(f"  {item.source_id} -> duplikat {item.duplicate_of}")
    with_district = sum(1 for item in listings if item.district)
    print(f"District recognized: {with_district}/{len(listings)}")
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

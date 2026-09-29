"""Load normalized listings into MySQL.

Run: uv run python -m etl.load
"""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import Listing, ListingImage
from etl.normalize import NormalizedListing

INPUT_FILE = Path("data/processed/listings.jsonl")

NORMALIZED_FIELDS = [
    "url",
    "title",
    "description",
    "price_pln",
    "price_per_m2",
    "rooms",
    "floor",
    "build_year",
    "market",
    "seller_type",
    "building_type",
    "ownership",
    "city",
    "location_raw",
    "extra_attributes",
    "flags",
    "duplicate_of",
]


def to_utc_naive(iso_timestamp: str) -> datetime:
    """MySQL DATETIME nie przechowuje strefy - trzymamy wszystko w UTC."""
    return datetime.fromisoformat(iso_timestamp).astimezone(UTC).replace(tzinfo=None)


def apply(listing: Listing, record: NormalizedListing) -> None:
    for field in NORMALIZED_FIELDS:
        setattr(listing, field, getattr(record, field))
    listing.area_m2 = Decimal(str(record.area_m2))
    listing.fetched_at = to_utc_naive(record.fetched_at)

    # District is either recognized from the raw location (rules) or filled in by AI.
    if record.district:
        listing.district, listing.district_source = record.district, "rules"
    elif listing.district_source != "ai":
        listing.district, listing.district_source = None, None

    listing.images = [
        ListingImage(url=url, position=position) for position, url in enumerate(record.images)
    ]


def upsert(session: Session, record: NormalizedListing) -> bool:
    """Zwraca True, jeśli oferta była nowa."""
    listing = session.scalar(
        select(Listing).where(
            Listing.source == record.source, Listing.source_id == record.source_id
        )
    )
    is_new = listing is None
    if is_new:
        listing = Listing(source=record.source, source_id=record.source_id)
        session.add(listing)
    apply(listing, record)
    return is_new


def main() -> None:
    lines = INPUT_FILE.read_text(encoding="utf-8").splitlines()
    records = [NormalizedListing.model_validate_json(line) for line in lines]

    with SessionLocal() as session, session.begin():
        created = sum(upsert(session, record) for record in records)

    print(
        f"Załadowano {len(records)} ofert (nowych: {created}, zaktualizowanych: "
        f"{len(records) - created})"
    )


if __name__ == "__main__":
    main()

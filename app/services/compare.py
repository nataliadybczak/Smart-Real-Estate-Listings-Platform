"""Side-by-side comparison of similar listings ("Compare with similar")."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.templates import FLAG_LABELS, LABELS, format_area, format_floor, format_number
from app.models import Listing

SIMILAR_TOLERANCE = 0.2 
MAX_COMPARED = 4


def similar_listings(db: Session, listing: Listing, limit: int = 3) -> list[Listing]:
    """Listings a buyer would weigh against this one: same rooms, similar price and area."""
    price, area = listing.price_pln, float(listing.area_m2)
    stmt = select(Listing).where(
        Listing.id != listing.id,
        Listing.duplicate_of.is_(None),
        Listing.price_pln.between(price * (1 - SIMILAR_TOLERANCE), price * (1 + SIMILAR_TOLERANCE)),
        Listing.area_m2.between(area * (1 - SIMILAR_TOLERANCE), area * (1 + SIMILAR_TOLERANCE)),
    )
    stmt = stmt.where(func.coalesce(func.json_length(Listing.flags), 0) == 0)  # trusted only
    if listing.rooms is not None:
        stmt = stmt.where(Listing.rooms == listing.rooms)
    # closest first: relative difference in price plus relative difference in area
    distance = func.abs(Listing.price_pln - price) / price + func.abs(Listing.area_m2 - area) / area
    return list(db.scalars(stmt.order_by(distance, Listing.id).limit(limit)))


def get_listings(db: Session, ids: list[int]) -> list[Listing]:
    """Listings in the order requested (the first one is the listing the user came from)."""
    ids = list(dict.fromkeys(ids))[:MAX_COMPARED]
    stmt = select(Listing).where(Listing.id.in_(ids)).options(selectinload(Listing.images))
    found = {listing.id: listing for listing in db.scalars(stmt)}
    return [found[listing_id] for listing_id in ids if listing_id in found]


Better = Literal["lower", "higher"] | Callable[[Any], bool] | None


@dataclass
class Row:
    label: str
    cells: list[str]
    best: list[bool]  # which columns hold the best value in this row
    differs: bool  # False -> hidden when "show only differences" is on
    ai: bool = False  # value extracted from the description by AI


@dataclass
class Attribute:
    label: str
    value: Callable[[Listing], Any]
    show: Callable[[Any], str]
    better: Better = None
    ai: bool = False


def _label(value: Any) -> str:
    return LABELS.get(value, value) if value and value != "unknown" else "–"


def _pln(value: Any) -> str:
    return f"{format_number(value)} PLN" if value is not None else "–"


ATTRIBUTES = [
    Attribute("Price", lambda x: x.price_pln, _pln, "lower"),
    Attribute("Price per m²", lambda x: x.price_per_m2, _pln, "lower"),
    Attribute("Area", lambda x: x.area_m2, format_area, "higher"),
    Attribute("Rooms", lambda x: x.rooms, lambda v: str(v) if v is not None else "–"),
    Attribute("Floor", lambda x: x.floor, format_floor),
    Attribute("District", lambda x: x.district, lambda v: v or "–"),
    Attribute("Market", lambda x: x.market, _label),
    Attribute("Year built", lambda x: x.build_year, lambda v: str(v) if v else "–"),
    Attribute("Condition", lambda x: x.condition, _label, ai=True),
    Attribute("Balcony / terrace", lambda x: x.balcony, _label, lambda v: v == "yes", ai=True),
    Attribute("Elevator", lambda x: x.elevator, _label, lambda v: v == "yes", ai=True),
    Attribute("Parking", lambda x: x.parking, _label, lambda v: v == "included", ai=True),
    Attribute("Furnished", lambda x: x.furnished, _label, ai=True),
    Attribute("Monthly fee", lambda x: x.monthly_fee_pln, _pln, "lower", ai=True),
    Attribute("Seller", lambda x: x.seller_type, _label),
    Attribute(
        "Data warnings",
        lambda x: tuple(x.flags or ()),
        lambda v: "; ".join(FLAG_LABELS.get(flag, flag) for flag in v) or "none",
        lambda v: not v,
    ),
]


def _best(values: list[Any], better: Better, trusted: list[bool]) -> list[bool]:
    """Best value in a row. Flagged listings (e.g. only a share of the flat) never "win"
    on numbers - their price is not comparable with a whole flat."""
    if better in ("lower", "higher"):
        values = [v if ok else None for v, ok in zip(values, trusted, strict=True)]
    if better is None:
        return [False] * len(values)
    if callable(better):  # e.g. balcony "yes" stands out unless every listing has one
        good = [better(v) for v in values]
        return good if not all(good) else [False] * len(values)
    known = [v for v in values if v is not None]
    if len(set(known)) < 2:  # nothing to choose between
        return [False] * len(values)
    numbers = [float(v) if isinstance(v, Decimal) else v for v in known]
    target = min(numbers) if better == "lower" else max(numbers)
    return [v in known and (float(v) if isinstance(v, Decimal) else v) == target for v in values]


def comparison_rows(listings: list[Listing]) -> list[Row]:
    trusted = [not listing.flags for listing in listings]
    rows = []
    for attribute in ATTRIBUTES:
        values = [attribute.value(listing) for listing in listings]
        cells = [attribute.show(value) for value in values]
        rows.append(
            Row(
                label=attribute.label,
                cells=cells,
                best=_best(values, attribute.better, trusted),
                differs=len(set(cells)) > 1,
                ai=attribute.ai,
            )
        )
    return rows

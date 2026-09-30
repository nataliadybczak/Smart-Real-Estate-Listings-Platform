"""Listing search logic - shared by the HTML pages, the JSON API and (later) the AI chat."""

import math
import re
from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.models import Listing
from app.schemas.listing import ListingFilters, SortOption

PAGE_SIZE = 12
MIN_SEARCH_TERM_LENGTH = 3  # MySQL default innodb_ft_min_token_size

SORT_ORDER = {
    SortOption.NEWEST: [Listing.source_id.desc()],  # Sprzedajemy IDs increase over time
    SortOption.PRICE_ASC: [Listing.price_pln.asc()],
    SortOption.PRICE_DESC: [Listing.price_pln.desc()],
    SortOption.PRICE_PER_M2_ASC: [Listing.price_per_m2.asc()],
    SortOption.AREA_DESC: [Listing.area_m2.desc()],
}


@dataclass
class SearchResult:
    items: list[Listing]
    total: int
    page: int
    pages: int


def fulltext_query(q: str) -> str | None:
    """Turn user input into a boolean-mode FULLTEXT query."""
    words = re.findall(r"\w+", q.lower())
    terms = [f"+{word}*" for word in words if len(word) >= MIN_SEARCH_TERM_LENGTH]
    return " ".join(terms) or None


def apply_filters(stmt: Select, filters: ListingFilters) -> Select:
    stmt = stmt.where(Listing.duplicate_of.is_(None))  # duplicates are hidden from the list

    if filters.q and (query := fulltext_query(filters.q)):
        match = text("MATCH (listings.title, listings.description) AGAINST (:q IN BOOLEAN MODE)")
        stmt = stmt.where(match.bindparams(q=query))
    if filters.district:
        stmt = stmt.where(Listing.district == filters.district)
    if filters.price_min is not None:
        stmt = stmt.where(Listing.price_pln >= filters.price_min)
    if filters.price_max is not None:
        stmt = stmt.where(Listing.price_pln <= filters.price_max)
    if filters.area_min is not None:
        stmt = stmt.where(Listing.area_m2 >= filters.area_min)
    if filters.area_max is not None:
        stmt = stmt.where(Listing.area_m2 <= filters.area_max)
    if filters.rooms:
        exact = [rooms for rooms in filters.rooms if rooms < 4]
        conditions = [Listing.rooms.in_(exact)]
        if any(rooms >= 4 for rooms in filters.rooms):  # "4" in the filter means "4 or more"
            conditions.append(Listing.rooms >= 4)
        stmt = stmt.where(or_(*conditions))
    if filters.market:
        stmt = stmt.where(Listing.market == filters.market)
    if filters.no_ground_floor:
        stmt = stmt.where(Listing.floor > 0)
    # AI-extracted fields: only an explicit "yes" from the description counts.
    feature_conditions = {
        "balcony": Listing.balcony == "yes",
        "elevator": Listing.elevator == "yes",
        "parking": Listing.parking.in_(["included", "extra_cost"]),
        "furnished": Listing.furnished.in_(["yes", "partly"]),
    }
    for feature in filters.features:
        stmt = stmt.where(feature_conditions[feature])
    if filters.condition:
        stmt = stmt.where(Listing.condition == filters.condition)
    return stmt


def search_listings(
    db: Session, filters: ListingFilters, page_size: int = PAGE_SIZE
) -> SearchResult:
    filtered = apply_filters(select(Listing), filters)
    total = db.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    pages = max(1, math.ceil(total / page_size))
    page = min(filters.page, pages)

    stmt = (
        filtered.options(selectinload(Listing.images))
        .order_by(*SORT_ORDER[filters.sort], Listing.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return SearchResult(items=list(db.scalars(stmt)), total=total, page=page, pages=pages)


def get_listing(db: Session, listing_id: int) -> Listing | None:
    stmt = select(Listing).where(Listing.id == listing_id).options(selectinload(Listing.images))
    return db.scalar(stmt)


def get_by_source_id(db: Session, source_id: str) -> Listing | None:
    return db.scalar(select(Listing).where(Listing.source_id == source_id))


def district_counts(db: Session) -> list[tuple[str, int]]:
    """Districts that actually occur in the data (for the filter dropdown)."""
    stmt = (
        select(Listing.district, func.count())
        .where(Listing.district.is_not(None), Listing.duplicate_of.is_(None))
        .group_by(Listing.district)
        .order_by(Listing.district)
    )
    return [(district, count) for district, count in db.execute(stmt)]

"""Discover duplicates in normalized listings.

Requirements for duplicates are only listings that are the same apartment, the same floor,
the same number of rooms, same area, very similar description and similar price.

Duplicates are marked in place by setting the `duplicate_of` attribute to the source_id
of the canonical listing.
"""

import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from etl.normalize import NormalizedListing

MAX_PRICE_DIFF_SECONDARY = 0.05
MAX_AREA_DIFF_M2 = 0.05
MIN_DESCRIPTION_SIMILARITY = 0.9


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()[:2000]


def descriptions_similar(a: str, b: str) -> bool:
    matcher = SequenceMatcher(None, _normalized_text(a), _normalized_text(b))
    return (
        matcher.quick_ratio() >= MIN_DESCRIPTION_SIMILARITY
        and matcher.ratio() >= MIN_DESCRIPTION_SIMILARITY
    )


def is_duplicate(a: "NormalizedListing", b: "NormalizedListing") -> bool:
    if (a.rooms, a.floor, a.market) != (b.rooms, b.floor, b.market):
        return False
    if abs(a.area_m2 - b.area_m2) > MAX_AREA_DIFF_M2:
        return False
    if a.market == "primary":
        if a.price_pln != b.price_pln:
            return False
    elif abs(a.price_pln - b.price_pln) / max(a.price_pln, b.price_pln) > MAX_PRICE_DIFF_SECONDARY:
        return False
    return descriptions_similar(a.description, b.description)


def _canonical_rank(listing: "NormalizedListing") -> tuple:
    filled = sum(value is not None for value in listing.model_dump().values())
    return (listing.seller_type != "private", -filled, listing.source_id)


def mark_duplicates(listings: list["NormalizedListing"]) -> None:
    ordered = sorted(listings, key=_canonical_rank)
    for i, candidate in enumerate(ordered):
        if candidate.duplicate_of:
            continue
        for other in ordered[i + 1 :]:
            if not other.duplicate_of and is_duplicate(candidate, other):
                other.duplicate_of = candidate.source_id

"""AI search: turn a vague request ("a nice, cheap flat, 40m") into our normal filters.

Split of responsibilities:
- the LLM only reads the sentence and fills a fixed schema (what the user said),
- deterministic rules decide what that means in our data (what we search for):
    "about 40 m²"  -> 35-45 m² (±12%),
    "cheap"        -> price per m² below the first quartile of clean listings,
    "nice"         -> condition "ready" or "renovated" (from AI enrichment).
So the meaning of "cheap" comes from the market data, not from the model's opinion,
and the result is an ordinary filtered search the user can inspect and adjust.
"""

import statistics
from collections.abc import Callable
from typing import Literal

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.llm import LLMNotConfiguredError, get_gemini_client
from app.schemas.listing import Feature, ListingFilters, SortOption
from app.services import listings as listing_service

AREA_TOLERANCE = 0.12  # "40 m²" is a rough wish, not an exact number


class AISearchError(RuntimeError):
    """The request could not be interpreted (LLM unavailable or invalid answer)."""


class SearchIntent(BaseModel):
    """What the user asked for, in their own terms. Everything is optional."""

    city: str | None = None
    district: str | None = None
    area_m2: float | None = Field(None, ge=1, le=999, description="approximate size wish")
    area_min_m2: float | None = Field(None, ge=1, le=999)
    area_max_m2: float | None = Field(None, ge=1, le=999)
    rooms: list[int] = Field(default_factory=list, description="1-4, 4 means 4 or more")
    price_max_pln: int | None = Field(None, ge=1)
    cheap: bool = False
    nice: bool = Field(False, description="nice / pretty / good condition / ready to move in")
    features: list[Feature] = Field(default_factory=list)
    market: Literal["primary", "secondary"] | None = None
    no_ground_floor: bool = False
    keywords: str | None = Field(None, description="other concrete words, e.g. a street name")


SYSTEM_INSTRUCTION = """You turn a flat-search request (English or Polish) into search parameters.
Only fill what the user actually asked for; leave everything else empty or false.
- "40m", "around 40 m2" -> area_m2=40. "between 40 and 60 m" -> area_min_m2/area_max_m2.
- "studio" / "kawalerka" -> rooms=[1]. "2-room" / "dwupokojowe" -> rooms=[2].
- "cheap", "affordable", "tanie", "okazja" -> cheap=true. A price limit -> price_max_pln.
- "nice", "pretty", "ładne", "in good condition", "ready to move in" -> nice=true.
- balcony / terrace -> "balcony"; lift -> "elevator"; garage / parking space -> "parking";
  furnished -> "furnished".
- "new build" / "od dewelopera" -> market=primary; "not on the ground floor" -> no_ground_floor.
- district: a Kraków district or area the user named (e.g. "Nowa Huta", "Kazimierz").
- keywords: only concrete words worth a text search (a street, an estate), else null."""


def parse_intent(text: str, client: genai.Client | None = None) -> SearchIntent:
    """Ask the LLM to read the request. Raises AISearchError when it cannot."""
    try:
        client = client or get_gemini_client()
        response = client.models.generate_content(
            model=get_settings().gemini_model,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=SearchIntent,
                temperature=0,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        return SearchIntent.model_validate_json(response.text or "")
    except (LLMNotConfiguredError, errors.APIError, ValidationError) as error:
        raise AISearchError(str(error)) from error


def cheap_threshold(price_per_m2_values: list[int]) -> int | None:
    """First quartile of price per m²: "cheaper than 75% of comparable listings"."""
    if len(price_per_m2_values) < 4:
        return None
    return round(statistics.quantiles(price_per_m2_values, n=4)[0])


def match_district(name: str | None, known_districts: list[str]) -> str | None:
    """Map what the user typed to a district that exists in our data (case-insensitive)."""
    if not name:
        return None
    wanted = name.strip().lower()
    for district in known_districts:
        if district.lower() == wanted or district.lower().startswith(wanted):
            return district
    return None


def intent_to_filters(
    intent: SearchIntent, *, cheap_max_ppm: int | None, known_districts: list[str]
) -> ListingFilters:
    """Deterministic rules: what the user's words mean in our data."""
    area_min, area_max = intent.area_min_m2, intent.area_max_m2
    if intent.area_m2 and not (area_min or area_max):
        area_min = round(intent.area_m2 * (1 - AREA_TOLERANCE))
        area_max = round(intent.area_m2 * (1 + AREA_TOLERANCE))

    district = match_district(intent.district, known_districts)
    # A named area we can't map to a district is still useful as a text search.
    keywords = intent.keywords or (intent.district if intent.district and not district else None)

    return ListingFilters(
        q=keywords,
        district=district,
        area_min=area_min,
        area_max=area_max,
        rooms=[min(rooms, 4) for rooms in intent.rooms if rooms > 0],
        price_max=intent.price_max_pln,
        price_per_m2_max=cheap_max_ppm if intent.cheap else None,
        good_condition=intent.nice,
        features=intent.features,
        market=intent.market,
        no_ground_floor=intent.no_ground_floor,
        sort=SortOption.PRICE_PER_M2_ASC if intent.cheap else SortOption.NEWEST,
    )


# Soft wishes we may drop, in this order, when nothing matches. Hard criteria (district,
# rooms, area, budget) are never dropped - an empty page is better than a wrong district.
RELAXATION_STEPS = [
    ("good_condition", False, "ready to move in or renovated"),
    ("features", [], "the requested features"),
    ("price_per_m2_max", None, "the “cheap” limit"),
]


def relax_until_results(
    filters: ListingFilters, count: Callable[[ListingFilters], int]
) -> tuple[ListingFilters, list[str]]:
    """Drop soft criteria one by one until something matches. Returns what was dropped."""
    dropped: list[str] = []
    for field, empty_value, label in RELAXATION_STEPS:
        if count(filters) > 0:
            break
        if getattr(filters, field) != empty_value:
            filters = filters.model_copy(update={field: empty_value})
            dropped.append(label)
    return filters, dropped


def interpret(db: Session, text: str) -> tuple[ListingFilters, list[str]]:
    """Full pipeline used by the web route: sentence -> intent -> filters (-> relaxed)."""
    intent = parse_intent(text)
    known = [name for name, _ in listing_service.district_counts(db)]
    threshold = cheap_threshold(listing_service.clean_price_per_m2_values(db))
    filters = intent_to_filters(intent, cheap_max_ppm=threshold, known_districts=known)
    filters, dropped = relax_until_results(
        filters, lambda f: listing_service.search_listings(db, f, page_size=1).total
    )
    return filters.model_copy(update={"ask": text}), dropped


FEATURE_LABELS = {
    "balcony": "with a balcony",
    "elevator": "with an elevator",
    "parking": "with parking",
    "furnished": "furnished",
}


def describe_filters(filters: ListingFilters) -> list[str]:
    """Plain-language list of what we actually searched for - shown back to the user."""
    parts: list[str] = []
    if filters.district:
        parts.append(filters.district)
    if filters.q:
        parts.append(f"“{filters.q}”")
    if filters.area_min and filters.area_max:
        parts.append(f"{filters.area_min:g}–{filters.area_max:g} m²")
    elif filters.area_min:
        parts.append(f"from {filters.area_min:g} m²")
    elif filters.area_max:
        parts.append(f"up to {filters.area_max:g} m²")
    if filters.rooms:
        labels = ["4+" if rooms >= 4 else str(rooms) for rooms in sorted(set(filters.rooms))]
        parts.append(f"{' or '.join(labels)} rooms")
    if filters.price_max:
        parts.append(f"up to {filters.price_max:,} PLN")
    if filters.price_per_m2_max:
        parts.append(f"up to {filters.price_per_m2_max:,} PLN/m² (cheapest 25% of the market)")
    if filters.good_condition:
        parts.append("ready to move in or renovated")
    parts += [FEATURE_LABELS[feature] for feature in filters.features]
    if filters.market:
        parts.append(f"{filters.market} market")
    if filters.no_ground_floor:
        parts.append("not on the ground floor")
    return parts


def filters_to_query(filters: ListingFilters) -> list[tuple[str, str]]:
    """Query-string pairs for a results URL (so the AI search is an ordinary, shareable link)."""
    pairs: list[tuple[str, str]] = []
    for name, value in filters.model_dump(exclude_defaults=True, mode="json").items():
        for item in value if isinstance(value, list) else [value]:
            pairs.append((name, "true" if item is True else str(item)))
    return pairs

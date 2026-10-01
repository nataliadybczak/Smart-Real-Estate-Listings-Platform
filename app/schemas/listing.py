"""Input/output schemas: search parameters and API responses."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SortOption(StrEnum):
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    PRICE_PER_M2_ASC = "ppm_asc"
    AREA_DESC = "area_desc"


Feature = Literal["balcony", "elevator", "parking", "furnished"]
Condition = Literal["developer", "ready", "renovated", "to_refresh", "to_renovate"]


class ListingFilters(BaseModel):
    """Search parameters from the filter sidebar (query string: ?price_max=800000&rooms=2...)."""

    model_config = ConfigDict(extra="ignore")

    q: str | None = Field(None, max_length=200, description="Search in title and description")
    district: str | None = None
    price_min: int | None = Field(None, ge=0)
    price_max: int | None = Field(None, ge=0)
    area_min: float | None = Field(None, ge=0)
    area_max: float | None = Field(None, ge=0)
    rooms: list[int] = Field(default_factory=list, description="4 means 4 or more")
    market: str | None = Field(None, pattern="^(primary|secondary)$")
    no_ground_floor: bool = False
    price_per_m2_max: int | None = Field(None, ge=0)
    good_condition: bool = Field(False, description="Ready to move in or renovated (AI)")
    features: list[Feature] = Field(default_factory=list, description="Extracted by AI")
    condition: Condition | None = Field(None, description="Extracted by AI")
    sort: SortOption = SortOption.NEWEST
    page: int = Field(1, ge=1)
    ask: str | None = Field(None, max_length=300, description="Original question from the AI chat")

    @field_validator("*", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        """HTML forms send empty fields as "" - treat them as "no filter"."""
        if value == "":
            return None
        if isinstance(value, list):
            return [item for item in value if item != ""]
        return value

    @field_validator("q")
    @classmethod
    def strip_query(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None

    def is_active(self) -> bool:
        """Whether the user set any filter (used to show the "clear filters" link)."""
        defaults = ListingFilters()
        return any(
            getattr(self, name) != getattr(defaults, name)
            for name in type(self).model_fields
            if name not in {"sort", "page", "ask"}
        )


class ListingImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    position: int


class ListingOut(BaseModel):
    """Listing as returned by the API (without internal technical fields)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str | None
    title: str
    price_pln: int
    area_m2: Decimal
    price_per_m2: int
    rooms: int | None
    floor: int | None
    build_year: int | None
    market: str | None
    seller_type: str | None
    city: str | None
    district: str | None
    location_raw: str | None
    flags: list[str]
    condition: str | None
    furnished: str | None
    balcony: str | None
    elevator: str | None
    parking: str | None
    monthly_fee_pln: int | None
    ai_summary: str | None
    fetched_at: datetime


class ListingDetailOut(ListingOut):
    description: str
    building_type: str | None
    ownership: str | None
    extra_attributes: dict[str, str]
    images: list[ListingImageOut]


class ListingPage(BaseModel):
    items: list[ListingOut]
    total: int
    page: int
    pages: int

"""Jinja2 template setup and formatting filters (numbers, labels, flags)."""

from decimal import Decimal
from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Database codes -> UI labels, kept in one place.
LABELS = {
    "primary": "primary market",
    "secondary": "secondary market",
    "agency": "agency / company",
    "private": "private seller",
    "developer": "developer standard",
    "ready": "ready to move in",
    "renovated": "renovated",
    "to_refresh": "needs refreshing",
    "to_renovate": "needs renovation",
}

FLAG_LABELS = {
    "price_per_m2_out_of_range": "unusual price per m² - possible error in the listing",
    "share_not_whole_flat": "only a share of the flat is for sale (co-ownership), not all of it",
    "rooms_implausible": "number of rooms does not match the floor area",
}


# Source (Polish) parameter names and values -> English. The set is small and closed
# (see data profiling), so a dictionary is enough; unknown values are shown as-is.
ATTRIBUTE_NAMES = {
    "Ogrzewanie": "Heating",
    "Materiał budynku": "Building material",
    "Liczba pięter": "Floors in building",
    "Pokrycie dachu": "Roof",
}
SOURCE_VALUES = {
    "blok": "block of flats",
    "kamienica": "tenement house",
    "apartamentowiec": "apartment building",
    "szeregówka": "terraced house",
    "własność": "full ownership",
    "spółdzielcze własnościowe": "cooperative ownership",
    "spółdzielcze własnościowe z KW": "cooperative ownership (with land register)",
    "udział": "share",
    "sieć": "district heating",
    "elektryczne": "electric",
    "gazowe": "gas",
    "cegła": "brick",
    "beton": "concrete",
    "wielka płyta": "large-panel concrete",
    "pustak": "hollow block",
    "inne": "other",
    "1 piętro": "1",
    "2 piętra": "2",
    "3 piętra i więcej": "3 or more",
    "blacha": "metal sheet",
    "papa": "roofing felt",
    "dachówka": "tiles",
}


def format_number(value: int | float | Decimal | None, decimals: int = 0) -> str:
    """669000 -> "669,000"."""
    if value is None:
        return "–"
    return f"{value:,.{decimals}f}"


def format_area(value: Decimal | float | None) -> str:
    if value is None:
        return "–"
    decimals = 0 if float(value).is_integer() else 2
    return f"{format_number(value, decimals)} m²"


def ordinal(value: int) -> str:
    """1 -> "1st", 2 -> "2nd", 11 -> "11th"."""
    if 11 <= value % 100 <= 13:
        return f"{value}th"
    return f"{value}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th') }"


def format_floor(value: int | None) -> str:
    if value is None:
        return "–"
    return {0: "ground floor", -1: "basement"}.get(value, f"{ordinal(value)} floor")


def rooms_label(value: int | None) -> str:
    if value is None:
        return "–"
    return "1 room" if value == 1 else f"{value} rooms"


def listings_count(value: int) -> str:
    return "1 listing" if value == 1 else f"{value} listings"


templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.filters.update(
    number=format_number,
    area=format_area,
    floor=format_floor,
    rooms=rooms_label,
    listings=listings_count,
    label=lambda code: LABELS.get(code, code) if code else "–",
    flag=lambda code: FLAG_LABELS.get(code, code),
    attr_name=lambda name: ATTRIBUTE_NAMES.get(name, name),
    source_value=lambda value: SOURCE_VALUES.get(value, value) if value else "–",
)

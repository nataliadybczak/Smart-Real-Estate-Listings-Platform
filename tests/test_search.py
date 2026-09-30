import pytest

from app.core.templates import format_area, format_floor, format_number, listings_count
from app.schemas.listing import ListingFilters
from app.services.listings import fulltext_query


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("balkon", "+balkon*"),
        ("Balkon, winda!", "+balkon* +winda*"),
        ("2 pok m2", "+pok*"),  # words shorter than 3 chars are ignored by MySQL anyway
        ('++")(', None),  # boolean-mode operators cannot break the query
    ],
)
def test_fulltext_query(text, expected):
    assert fulltext_query(text) == expected


def test_empty_form_fields_are_ignored():
    filters = ListingFilters.model_validate({"price_min": "", "q": "  ", "rooms": ["", "2"]})
    assert filters.price_min is None
    assert filters.q is None
    assert filters.rooms == [2]
    assert filters.is_active()


def test_default_filters_are_not_active():
    assert not ListingFilters().is_active()


def test_formatting():
    assert format_number(669000) == "669,000"
    assert format_area(47.85) == "47.85 m²"
    assert [format_floor(n) for n in (0, 1, 2, 3, 11, 22)] == [
        "ground floor",
        "1st floor",
        "2nd floor",
        "3rd floor",
        "11th floor",
        "22nd floor",
    ]
    assert listings_count(1) == "1 listing"
    assert listings_count(146) == "146 listings"


def test_source_values_are_translated_and_unknown_kept():
    from app.core.templates import templates

    translate = templates.env.filters["source_value"]
    assert translate("blok") == "block of flats"
    assert translate("coś nowego") == "coś nowego"

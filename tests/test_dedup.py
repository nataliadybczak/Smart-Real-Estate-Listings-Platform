from etl.dedup import mark_duplicates
from etl.normalize import normalize_record
from tests.test_normalize import raw_offer

LONG_DESCRIPTION = "Mieszkanie w nowej inwestycji, blisko tramwaju i parku. " * 20


def offer(source_id: str, price: str, area: str, market: str = "wtórny", seller: str = "firmy"):
    attributes = raw_offer()["attributes"] | {
        "Powierzchnia": area,
        "Rynek": market,
        "Oferta od": seller,
    }
    return normalize_record(
        raw_offer(
            source_id=source_id, price=price, attributes=attributes, description=LONG_DESCRIPTION
        )
    )


def test_same_flat_from_owner_and_agency_is_duplicate_and_owner_is_kept():
    agency = offer("1", "555000", "40 m²", seller="firmy")
    owner = offer("2", "540000", "40 m²", seller="osoby prywatnej")
    mark_duplicates([agency, owner])
    assert owner.duplicate_of is None
    assert agency.duplicate_of == "2"


def test_developer_template_description_with_different_area_is_not_duplicate():
    first = offer("1", "645876", "35.21 m²", market="pierwotny")
    second = offer("2", "672124", "35.31 m²", market="pierwotny")
    mark_duplicates([first, second])
    assert first.duplicate_of is None and second.duplicate_of is None


def test_primary_market_requires_identical_price():
    first = offer("1", "645876", "35.21 m²", market="pierwotny")
    second = offer("2", "645693", "35.21 m²", market="pierwotny")
    mark_duplicates([first, second])
    assert second.duplicate_of is None

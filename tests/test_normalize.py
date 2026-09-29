from typing import Any

from etl.normalize import NormalizedListing, RejectedRecord, normalize_record


def raw_offer(
    *,
    source_id: str = "70118167",
    title: str = "os Kazimierzowskie - mieszkanie 2 pokojowe",
    price: str = "515000.00",
    currency: str = "PLN",
    description: str = "Mieszkanie 2 pokojowe na VIII piętrze. Blok z windą.",
    attributes: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "source": "sprzedajemy",
        "source_id": source_id,
        "url": f"https://sprzedajemy.pl/mieszkanie-nr{source_id}",
        "fetched_at": "2026-09-28T22:19:46.999196+00:00",
        "title": title,
        "description": description,
        "price": price,
        "currency": currency,
        "city": "Kraków",
        "district": "Bieńczyce",
        "images": [],
        "attributes": attributes
        if attributes is not None
        else {
            "Oferta od": "firmy",
            "Rynek": "wtórny",
            "Cena za m²": "13918 zł/m²",
            "Powierzchnia": "37 m²",
            "Zabudowa": "blok",
            "Liczba pokoi": "2",
            "Ogrzewanie": "sieć",
            "Rok budowy": "1980",
            "Forma własności": "spółdzielcze własnościowe",
            "Piętro": "8",
        },
    }


def test_valid_offer_is_normalized_into_typed_fields():
    listing = normalize_record(raw_offer())
    assert isinstance(listing, NormalizedListing)
    assert listing.price_pln == 515000
    assert listing.area_m2 == 37
    assert listing.price_per_m2 == 13919
    assert (listing.rooms, listing.floor, listing.build_year) == (2, 8, 1980)
    assert (listing.market, listing.seller_type) == ("secondary", "agency")
    assert listing.extra_attributes == {"Ogrzewanie": "sieć"}
    assert listing.flags == []


def test_ground_floor_is_zero():
    attributes = raw_offer()["attributes"] | {"Piętro": "parter"}
    listing = normalize_record(raw_offer(attributes=attributes))
    assert listing.floor == 0


def test_non_pln_currency_is_rejected():
    result = normalize_record(raw_offer(currency="EUR"))
    assert result == RejectedRecord(source_id="70118167", reason="currency_not_pln")


def test_house_is_rejected():
    result = normalize_record(raw_offer(title="Dom wolnostojący z ogrodem"))
    assert isinstance(result, RejectedRecord)
    assert result.reason == "not_an_apartment"


def test_missing_area_is_rejected():
    result = normalize_record(raw_offer(attributes={"Rynek": "wtórny"}))
    assert isinstance(result, RejectedRecord)
    assert result.reason == "missing_price_or_area"


def test_share_in_flat_is_flagged():
    listing = normalize_record(raw_offer(title="1/2 udział w mieszkaniu"))
    assert "share_not_whole_flat" in listing.flags

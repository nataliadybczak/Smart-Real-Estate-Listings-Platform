from decimal import Decimal
from types import SimpleNamespace

from app.services.compare import comparison_rows


def listing(**fields):
    base = {
        "price_pln": 500_000, "price_per_m2": 12_500, "area_m2": Decimal("40.00"), "rooms": 2,
        "floor": 1, "district": "Bronowice", "market": "secondary", "build_year": 2000,
        "condition": "unknown", "balcony": "unknown", "elevator": "unknown",
        "parking": "unknown", "furnished": "unknown", "monthly_fee_pln": None,
        "seller_type": "agency", "flags": [],
    }  # fmt: skip
    return SimpleNamespace(**(base | fields))


def row(rows, label):
    return next(r for r in rows if r.label == label)


def test_best_values_are_marked_per_row():
    rows = comparison_rows(
        [listing(), listing(price_pln=480_000, balcony="yes", area_m2=Decimal("38.50"))]
    )
    assert row(rows, "Price").best == [False, True]
    assert row(rows, "Area").best == [True, False]
    assert row(rows, "Balcony / terrace").best == [False, True]


def test_identical_and_unknown_values_are_not_differences():
    rows = comparison_rows([listing(), listing()])
    assert not row(rows, "Rooms").differs
    assert row(rows, "Monthly fee").cells == ["–", "–"]
    assert row(rows, "Monthly fee").best == [False, False]  # nothing known, no winner


def test_flagged_listing_never_wins_on_price():
    share = listing(price_pln=50_000, price_per_m2=1_250, flags=["share_not_whole_flat"])
    rows = comparison_rows([listing(), share, listing(price_pln=520_000)])
    assert row(rows, "Price").best == [True, False, False]
    assert row(rows, "Data warnings").best == [True, False, True]

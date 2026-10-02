import json
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.schemas.listing import ListingFilters, SortOption
from app.services.ai_search import (
    AISearchError,
    SearchIntent,
    cheap_threshold,
    describe_filters,
    filters_to_query,
    household_rooms,
    intent_to_filters,
    parse_intent,
    share_living_room,
)

DISTRICTS = ["Bronowice", "Nowa Huta", "Stare Miasto"]


def to_filters(**intent) -> ListingFilters:
    return intent_to_filters(SearchIntent(**intent), cheap_max_ppm=14536, known_districts=DISTRICTS)


def test_nice_cheap_40m_example_from_the_task():
    filters = to_filters(city="Kraków", area_m2=40, cheap=True, nice=True)
    assert (filters.area_min, filters.area_max) == (35, 45)
    assert filters.price_per_m2_max == 14536
    assert filters.good_condition
    assert filters.sort == SortOption.PRICE_PER_M2_ASC


def test_explicit_range_wins_over_approximate_size():
    filters = to_filters(area_m2=50, area_min_m2=40, area_max_m2=60)
    assert (filters.area_min, filters.area_max) == (40, 60)


def test_not_cheap_means_no_price_per_m2_limit():
    assert to_filters(area_m2=40).price_per_m2_max is None


def test_known_district_is_a_filter_unknown_area_becomes_text_search():
    assert to_filters(district="nowa huta").district == "Nowa Huta"
    filters = to_filters(district="Kazimierz")
    assert filters.district is None and filters.q == "Kazimierz"


def test_rooms_above_four_mean_four_or_more():
    assert to_filters(rooms=[2, 6]).rooms == [2, 4]


def test_cheap_threshold_is_first_quartile():
    assert cheap_threshold([10, 20, 30, 40, 50, 60, 70, 80]) == 22  # exclusive method: 22.5
    assert cheap_threshold([10, 20]) is None


def test_description_and_query_string():
    filters = to_filters(area_m2=40, cheap=True, features=["balcony"])
    assert describe_filters(filters) == [
        "35–45 m²",
        "up to 14,536 PLN/m² (cheapest 25% of the market)",
        "with a balcony",
    ]
    assert ("features", "balcony") in filters_to_query(filters)
    assert ("sort", "ppm_asc") in filters_to_query(filters)


def fake_client(result):
    def generate_content(**kwargs):
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(text=result)

    return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))


def test_parse_intent_reads_the_model_answer():
    answer = json.dumps({"area_m2": 40, "cheap": True, "nice": True})
    assert parse_intent("nice cheap 40m", client=fake_client(answer)).area_m2 == 40


@pytest.mark.parametrize(
    "result", [errors.ServerError(503, {"error": {}}), json.dumps({"rooms": "many"})]
)
def test_llm_failure_becomes_ai_search_error(result):
    with pytest.raises(AISearchError):
        parse_intent("anything", client=fake_client(result))


def test_soft_criteria_are_relaxed_in_order_until_something_matches():
    from app.services.ai_search import relax_until_results

    filters = to_filters(area_m2=40, cheap=True, nice=True, features=["balcony"])
    # pretend results appear only once good_condition AND features are dropped
    count = lambda f: 0 if (f.good_condition or f.features) else 5  # noqa: E731
    relaxed, dropped = relax_until_results(filters, count)
    assert dropped == ["ready to move in or renovated", "the requested features"]
    assert relaxed.price_per_m2_max == 14536  # "cheap" kept - it was not needed to drop it
    assert (relaxed.area_min, relaxed.area_max) == (35, 45)  # hard criteria never dropped


def test_nothing_is_relaxed_when_there_are_results():
    from app.services.ai_search import relax_until_results

    filters = to_filters(nice=True)
    assert relax_until_results(filters, lambda f: 3) == (filters, [])


def test_couple_working_from_home_needs_four_rooms():
    intent = SearchIntent(bedrooms_needed=1, home_offices_needed=2)
    assert household_rooms(intent).explain() == (
        "1 bedroom + 2 home offices + a living room = 4 rooms"
    )
    assert to_filters(bedrooms_needed=1, home_offices_needed=2).rooms == [4]


def test_two_flatmates_need_two_bedrooms_and_a_living_room():
    filters = to_filters(bedrooms_needed=2)
    assert filters.rooms == [3, 4]
    assert describe_filters(filters) == ["3+ rooms"]


def test_explicit_room_count_wins_over_household():
    intent = SearchIntent(rooms=[2], bedrooms_needed=2)
    assert household_rooms(intent) is None
    assert to_filters(rooms=[2], bedrooms_needed=2).rooms == [2]


def test_household_falls_back_to_one_room_fewer_when_nothing_matches():
    household = household_rooms(SearchIntent(bedrooms_needed=1, home_offices_needed=2))
    filters = to_filters(bedrooms_needed=1, home_offices_needed=2)
    relaxed, dropped = share_living_room(filters, household, lambda f: 0)
    assert relaxed.rooms == [3, 4]
    assert "living room" in dropped
    assert share_living_room(filters, household, lambda f: 2) == (filters, None)

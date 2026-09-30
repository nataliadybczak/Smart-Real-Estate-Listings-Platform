import json
from decimal import Decimal
from types import SimpleNamespace

import pytest
from google.genai import errors
from pydantic import ValidationError

from app.models import Listing
from etl import enrich
from etl.enrich import ListingEnrichment, apply_enrichment, build_prompt, call_model

VALID_ANSWER = {
    "condition": "to_refresh",
    "furnished": "no",
    "balcony": "yes",
    "elevator": "no",
    "parking": "unknown",
    "monthly_fee_pln": 869,
    "district": "Nowa Huta",
    "summary_en": "Two-room flat in need of refreshing, with a large loggia and a cellar.",
}


class FakeModels:
    """Stands in for client.models: returns queued answers or raises queued errors."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(text=result)


def fake_client(*results):
    return SimpleNamespace(models=FakeModels(*results))


def listing(**overrides) -> Listing:
    fields = {
        "title": "2 pokoje / loggia",
        "description": "Opis mieszkania. Czynsz: 869 zł.",
        "price_pln": 669000,
        "area_m2": Decimal("51.00"),
        "rooms": 2,
        "floor": 1,
        "market": "secondary",
        "location_raw": "Nowa Huta",
        "district": None,
        "district_source": None,
    }
    return Listing(**(fields | overrides))


def test_valid_answer_is_parsed():
    result = call_model(fake_client(json.dumps(VALID_ANSWER)), "model", "prompt")
    assert result.monthly_fee_pln == 869


def test_answer_outside_schema_is_rejected():
    bad = VALID_ANSWER | {"balcony": "probably"}
    with pytest.raises(ValidationError):
        call_model(fake_client(json.dumps(bad)), "model", "prompt")


def test_rate_limit_is_retried(monkeypatch):
    monkeypatch.setattr(enrich.time, "sleep", lambda seconds: None)
    client = fake_client(errors.ClientError(429, {"error": {}}), json.dumps(VALID_ANSWER))
    assert call_model(client, "model", "prompt").balcony == "yes"
    assert client.models.calls == 2


def test_overloaded_model_is_retried(monkeypatch):
    monkeypatch.setattr(enrich.time, "sleep", lambda seconds: None)
    client = fake_client(errors.ServerError(503, {"error": {}}), json.dumps(VALID_ANSWER))
    assert call_model(client, "model", "prompt").condition == "to_refresh"


def test_permanent_error_is_not_retried():
    client = fake_client(errors.ClientError(400, {"error": {}}))
    with pytest.raises(errors.ClientError):
        call_model(client, "model", "prompt")
    assert client.models.calls == 1


def test_ai_fills_missing_district_and_marks_the_source():
    item = listing()
    apply_enrichment(item, ListingEnrichment(**VALID_ANSWER))
    assert (item.district, item.district_source) == ("Nowa Huta", "ai")
    assert item.ai_enriched_at is not None


def test_district_from_rules_is_never_overwritten():
    item = listing(district="Bieńczyce", district_source="rules")
    apply_enrichment(item, ListingEnrichment(**VALID_ANSWER))
    assert (item.district, item.district_source) == ("Bieńczyce", "rules")


def test_made_up_district_is_dropped():
    item = listing()
    apply_enrichment(item, ListingEnrichment(**(VALID_ANSWER | {"district": "Olsza"})))
    assert item.district is None


def test_shared_parking_is_a_valid_answer():
    assert ListingEnrichment(**(VALID_ANSWER | {"parking": "shared"})).parking == "shared"


def test_prompt_contains_known_facts_and_description():
    prompt = build_prompt(listing())
    assert "price_pln=669000" in prompt and "Czynsz: 869" in prompt

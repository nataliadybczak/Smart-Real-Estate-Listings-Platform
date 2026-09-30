"""AI enrichment: extract facts that exist only in the free-text description.


Usage:
    uv run python -m etl.enrich --limit 3 --dry-run   # try on 3 listings, save nothing
    uv run python -m etl.enrich                       # enrich everything not done yet
"""

import argparse
import time
from datetime import UTC, datetime
from typing import Literal

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.llm import get_gemini_client
from app.models import Listing
from etl.districts import KRAKOW_DISTRICTS

MAX_DESCRIPTION_CHARS = 6000  # longest descriptions are ~9k chars; the key facts come first
REQUEST_DELAY_SECONDS = 4.5  # stays under ~15 requests/minute on the free tier
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 20  # waits 20s, 40s, 60s, 80s between attempts

Tristate = Literal["yes", "no", "unknown"]


class ListingEnrichment(BaseModel):
    """The only shape the model is allowed to answer with."""

    condition: Literal["developer", "ready", "renovated", "to_refresh", "to_renovate", "unknown"]
    furnished: Literal["yes", "partly", "no", "unknown"]
    balcony: Tristate = Field(description="balcony, loggia or terrace")
    elevator: Tristate
    parking: Literal["included", "extra_cost", "shared", "no", "unknown"]
    monthly_fee_pln: int | None = Field(
        None, ge=0, le=10_000, description="monthly service charge (czynsz) in PLN"
    )
    district: str | None = Field(None, description="one of the official Kraków districts")
    summary_en: str = Field(max_length=400, description="1-2 factual sentences in English")


SYSTEM_INSTRUCTION = f"""You extract facts from Polish real-estate listings in Kraków.
Rules:
- Use ONLY information explicitly stated in the listing.
  If something is not stated, answer "unknown" (or null).
- Do not treat marketing language as facts ("ogromny potencjał" is not a condition).
- condition: developer = "stan deweloperski" / to be finished; ready = finished, ready to move in;
  renovated = "po remoncie"; to_refresh = "do odświeżenia"; to_renovate = "do remontu".
- balcony / elevator: answer "no" ONLY when the listing says so explicitly
  ("Balkon: brak", "brak windy", "Winda: NIE") or the balcony is a French balcony
  ("balkon francuski"). Not mentioned at all -> "unknown", never "no".
- parking: included = a dedicated space/garage belongs to the flat at no extra price
  (e.g. "miejsce postojowe" listed among the flat's features);
  extra_cost = a dedicated space can be bought or rented extra;
  shared = only communal or street parking; no = the listing says there is no parking.
- furnished: "yes" only if furniture is mentioned ("umeblowane", "meble");
  fittings or appliances alone ("wyposażenie", AGD, zabudowa kuchenna) -> "partly".
- monthly_fee_pln: the monthly service charge ("czynsz", "opłaty administracyjne"), not the price.
- district: one of {", ".join(KRAKOW_DISTRICTS)}.
  Use the district named in the listing, or infer it from a well-known street, estate
  ("osiedle") or landmark in Kraków. If the location is ambiguous or missing, answer null.
- summary_en: 1-2 neutral, factual sentences in English for someone who does not speak Polish.
  No marketing, no exclamation marks.
  Mention the most useful facts (size, rooms, condition, extras)."""


def build_prompt(listing: Listing) -> str:
    known = {
        "price_pln": listing.price_pln,
        "area_m2": float(listing.area_m2),
        "rooms": listing.rooms,
        "floor": listing.floor,
        "market": listing.market,
        "location": listing.location_raw,
    }
    known_text = ", ".join(f"{key}={value}" for key, value in known.items() if value is not None)
    return (
        f"Known structured data (already verified, do not contradict): {known_text}\n\n"
        f"Title: {listing.title}\n\n"
        f"Description:\n{listing.description[:MAX_DESCRIPTION_CHARS]}"
    )


def is_transient(error: errors.APIError) -> bool:
    """429 = rate limit, 5xx = model overloaded / server issue - worth retrying later."""
    return error.code == 429 or (error.code or 0) >= 500


def call_model(client: genai.Client, model: str, prompt: str) -> ListingEnrichment:
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=ListingEnrichment,
        temperature=0,  # extraction, not creativity - make answers repeatable
        # we don't use tools - disabling this also silences an SDK warning
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
            # Validate ourselves instead of trusting the model: bad output raises ValidationError.
            return ListingEnrichment.model_validate_json(response.text or "")
        except errors.APIError as error:
            if not is_transient(error) or attempt == MAX_RETRIES:
                raise
            wait = RETRY_BACKOFF_SECONDS * (attempt + 1)
            print(f"    {error.code} from the API (temporary), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def apply_enrichment(listing: Listing, enrichment: ListingEnrichment) -> None:
    """Write AI answers into the listing, respecting data from structured sources."""
    listing.condition = enrichment.condition
    listing.furnished = enrichment.furnished
    listing.balcony = enrichment.balcony
    listing.elevator = enrichment.elevator
    listing.parking = enrichment.parking
    listing.monthly_fee_pln = enrichment.monthly_fee_pln
    listing.ai_summary = enrichment.summary_en.strip() or None

    # District: rules win; AI only fills gaps and only with an official district name.
    if listing.district_source != "rules":
        valid = enrichment.district in KRAKOW_DISTRICTS
        listing.district = enrichment.district if valid else None
        listing.district_source = "ai" if valid else None

    listing.ai_enriched_at = datetime.now(UTC).replace(tzinfo=None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich listings with facts extracted by AI")
    parser.add_argument("--limit", type=int, help="process at most N listings")
    parser.add_argument("--force", action="store_true", help="re-process already enriched ones")
    parser.add_argument("--dry-run", action="store_true", help="print results, save nothing")
    parser.add_argument("--model", help="override GEMINI_MODEL for this run")
    args = parser.parse_args()

    settings = get_settings()
    model = args.model or settings.gemini_model
    client = get_gemini_client()

    with SessionLocal() as session:
        stmt = select(Listing).where(Listing.duplicate_of.is_(None)).order_by(Listing.id)
        if not args.force:
            stmt = stmt.where(Listing.ai_enriched_at.is_(None))
        if args.limit:
            stmt = stmt.limit(args.limit)
        listings = list(session.scalars(stmt))
        print(f"Model: {model} | listings to process: {len(listings)}")

        done, failed = 0, 0
        for i, listing in enumerate(listings, start=1):
            try:
                enrichment = call_model(client, model, build_prompt(listing))
            except (errors.APIError, ValidationError) as error:
                failed += 1
                print(f"[{i}/{len(listings)}] #{listing.id} FAILED: {error}")
                continue
            print(f"[{i}/{len(listings)}] #{listing.id} {enrichment.model_dump_json()}")
            if not args.dry_run:
                apply_enrichment(listing, enrichment)
                session.commit()  # save after each listing - an interruption loses nothing
            done += 1
            time.sleep(REQUEST_DELAY_SECONDS)

    mode = " (dry run - nothing saved)" if args.dry_run else ""
    print(f"\nDone: {done} enriched, {failed} failed{mode}")


if __name__ == "__main__":
    main()

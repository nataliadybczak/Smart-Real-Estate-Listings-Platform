# Smart-Real-Estate-Listings-Platform

A listings platform for flats in Kraków: ~150 real offers scraped from Sprzedajemy.pl, cleaned, deduplicated and stored in MySQL. You can search them in three ways: filters (including facts AI extracted from the descriptions), an AI chat that understands your situation, and a side-by-side comparison of similar offer

**Live demo:** https://smart-listings.onrender.com

**Reasoning document:** [reasoning_document.md](reasoning_document.md)

## What it does 

### Search and filters
- Full-text search in titles and descriptions (listings are in Polish).
- Filters: district, price, price per m², area, rooms (1 / 2 / 3 / 4+), market, no ground floor.
- **Filters from descriptions (AI):** balcony, elevator, parking, furnished and condition –
  facts that exist only in the seller's free text. Only an explicit “yes” matches; a listing that
  doesn't mention an elevator is “unknown”, never “no”.
- Sorting (newest, price, price per m², area) and pagination.

### AI chat search
- Describe what you want in plain English or Polish.
- The answer shows what was searched for. If nothing matches, soft wishes are dropped one by one
  (condition, features, “cheap”, then one room) and the chat says what it dropped.
- The result is ordinary filters the user can adjust. If the model is unavailable, the page says
  so and the filters keep working.

### Offer page
- Photo gallery, all parameters, an AI summary in English and the facts read from the
  description (labelled AI).
- Data-quality warnings (e.g. an unusual price per m², only a share of the flat for sale) and
  a link to the original listing when this one is a duplicate.
- “Contact the seller” links to the source listing.

### Compare with similar
- From any offer: up to 3 similar listings (same rooms, price and area within ±20%,
  no duplicates or flagged listings) side by side.
- The best value in each row is highlighted (price, price per m², area, monthly fee, balcony…);
  flagged listings never “win” on price.
- “Show only differences” hides rows where all listings are the same.

## Stack
 
Python 3.12, FastAPI + Jinja2 (server-rendered pages), SQLAlchemy + Alembic, MySQL 8.4,
httpx + selectolax (scraping), Google Gemini (free tier) for AI, uv, ruff, pytest.

## Run locally
Requirements: uv, Docker.

```
cp .env.example .env              # add GEMINI_API_KEY to enable AI features (optional)
docker compose up -d              # MySQL 8.4
uv sync
uv run alembic upgrade head
uv run python -m etl.load         # loads data/processed/listings.jsonl
uv run python -m etl.enrich       # optional: AI enrichment (free Gemini key)
uv run uvicorn app.main:app --reload --reload-dir app
```

Open http://localhost:8000. Without a Gemini key the app works fully except the AI fields (empty) and the chat search.

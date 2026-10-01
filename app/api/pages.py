"""HTML pages: listing search with filters and listing details."""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.db import DbSession
from app.core.templates import templates
from app.schemas.listing import ListingFilters, SortOption
from app.services import ai_search
from app.services import listings as listing_service

router = APIRouter(include_in_schema=False)

SORT_LABELS = {
    SortOption.NEWEST: "Newest",
    SortOption.PRICE_ASC: "Price: low to high",
    SortOption.PRICE_DESC: "Price: high to low",
    SortOption.PRICE_PER_M2_ASC: "Price per m²: low to high",
    SortOption.AREA_DESC: "Area: largest first",
}


def page_url(request: Request, page: int) -> str:
    """Link to another results page, keeping all current filters."""
    params = [(key, value) for key, value in request.query_params.multi_items() if key != "page"]
    return f"{request.url.path}?{urlencode([*params, ('page', page)])}"


@router.get("/", response_class=HTMLResponse)
def listing_page(
    request: Request, db: DbSession, filters: Annotated[ListingFilters, Query()]
) -> HTMLResponse:
    result = listing_service.search_listings(db, filters)
    return templates.TemplateResponse(
        request,
        "listings.html",
        {
            "filters": filters,
            "result": result,
            "districts": listing_service.district_counts(db),
            "understood": ai_search.describe_filters(filters) if filters.ask else [],
            "ai_error": request.query_params.get("ai_error") == "1",
            "relaxed": request.query_params.getlist("relaxed") if filters.ask else [],
            "sort_labels": SORT_LABELS,
            "page_url": lambda page: page_url(request, page),
        },
    )


@router.get("/ask")
def ask(db: DbSession, text: Annotated[str, Query(max_length=300)] = "") -> RedirectResponse:
    """AI search: interpret the sentence, then show ordinary filtered results for it."""
    text = text.strip()
    if not text:
        return RedirectResponse("/", status_code=303)
    try:
        filters, dropped = ai_search.interpret(db, text)
    except ai_search.AISearchError:
        # The LLM is optional: without it the user still gets the normal search page.
        return RedirectResponse(f"/?{urlencode({'ask': text, 'ai_error': '1'})}", status_code=303)
    params = ai_search.filters_to_query(filters) + [("relaxed", label) for label in dropped]
    return RedirectResponse(f"/?{urlencode(params)}", status_code=303)


@router.get("/listings/{listing_id}", response_class=HTMLResponse)
def listing_detail_page(request: Request, db: DbSession, listing_id: int) -> HTMLResponse:
    listing = listing_service.get_listing(db, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    original = (
        listing_service.get_by_source_id(db, listing.duplicate_of) if listing.duplicate_of else None
    )
    return templates.TemplateResponse(
        request, "listing_detail.html", {"listing": listing, "original": original}
    )

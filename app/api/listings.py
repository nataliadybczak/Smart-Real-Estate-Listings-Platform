"""Listings JSON API - same logic as the HTML pages; documented at /docs."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core.db import DbSession
from app.schemas.listing import ListingDetailOut, ListingFilters, ListingOut, ListingPage
from app.services import listings as listing_service

router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.get("", response_model=ListingPage)
def list_listings(db: DbSession, filters: Annotated[ListingFilters, Query()]) -> ListingPage:
    result = listing_service.search_listings(db, filters)
    return ListingPage(
        items=[ListingOut.model_validate(item) for item in result.items],
        total=result.total,
        page=result.page,
        pages=result.pages,
    )


@router.get("/{listing_id}", response_model=ListingDetailOut)
def get_listing(db: DbSession, listing_id: int) -> ListingDetailOut:
    listing = listing_service.get_listing(db, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return ListingDetailOut.model_validate(listing)

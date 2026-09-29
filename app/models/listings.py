"""
Models for the database tables.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_listings_source"),
        Index("ix_listings_title_description_ft", "title", "description", mysql_prefix="FULLTEXT"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    source: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(32))
    url: Mapped[str | None] = mapped_column(String(500))
    fetched_at: Mapped[datetime] = mapped_column(DateTime)

    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)

    # Normalized parameters from structural fields
    price_pln: Mapped[int] = mapped_column(Integer, index=True)
    area_m2: Mapped[Decimal] = mapped_column(Numeric(7, 2), index=True)
    price_per_m2: Mapped[int] = mapped_column(Integer)
    rooms: Mapped[int | None] = mapped_column(SmallInteger, index=True)
    floor: Mapped[int | None] = mapped_column(SmallInteger)
    build_year: Mapped[int | None] = mapped_column(SmallInteger)
    market: Mapped[str | None] = mapped_column(String(16), index=True)
    seller_type: Mapped[str | None] = mapped_column(String(16))
    building_type: Mapped[str | None] = mapped_column(String(50))
    ownership: Mapped[str | None] = mapped_column(String(80))

    # Location
    city: Mapped[str | None] = mapped_column(String(80), index=True)
    district: Mapped[str | None] = mapped_column(String(80), index=True)
    district_source: Mapped[str | None] = mapped_column(String(8))
    location_raw: Mapped[str | None] = mapped_column(String(200))

    # Quality of data
    extra_attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    duplicate_of: Mapped[str | None] = mapped_column(String(32))

    # Fields filled by AI - NULL = not yet processed
    condition: Mapped[str | None] = mapped_column(String(16))
    furnished: Mapped[str | None] = mapped_column(String(8))
    balcony: Mapped[str | None] = mapped_column(String(8))
    elevator: Mapped[str | None] = mapped_column(String(8))
    parking: Mapped[str | None] = mapped_column(String(12))
    monthly_fee_pln: Mapped[int | None] = mapped_column(Integer)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_enriched_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    images: Mapped[list["ListingImage"]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="ListingImage.position",
    )


class ListingImage(Base):
    __tablename__ = "listing_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(SmallInteger)

    listing: Mapped[Listing] = relationship(back_populates="images")

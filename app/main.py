from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import listings, pages
from app.core.db import DbSession
from app.core.errors import register_error_handlers

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Smart Real Estate Listings")
register_error_handlers(app)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(pages.router)
app.include_router(listings.router)


@app.get("/health", tags=["system"])
def health(db: DbSession) -> dict[str, str]:
    """Liveness check: the app is running and can reach the database."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}

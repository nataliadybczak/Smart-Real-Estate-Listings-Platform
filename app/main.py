from fastapi import FastAPI
from sqlalchemy import text

from app.core.db import DbSession

app = FastAPI(title="Smart Real Estate Listings")


@app.get("/health")
def health(db: DbSession) -> dict[str, str]:
    """Prosty test: czy aplikacja żyje i czy dogaduje się z bazą."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session

app = FastAPI(title="Evolve CRM API")


@app.get("/api/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    settings = get_settings()
    return {
        "status": "ok",
        "database": "ok",
        "environment": settings.environment,
        "release": settings.release,
    }

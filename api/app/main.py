from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import get_settings
from app.db import SessionLocal, get_session
from app.models import User
from app.routers import auth, companies, contacts, deals


def ensure_admin_exists() -> None:
    """A fresh installation has no users; create the first admin from the environment."""
    settings = get_settings()
    with SessionLocal() as session:
        if session.scalar(select(func.count(User.id))) == 0:
            session.add(
                User(
                    email=settings.admin_email,
                    name="Admin",
                    role="admin",
                    password_hash=hash_password(settings.admin_password),
                )
            )
            session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_admin_exists()
    yield


app = FastAPI(title="Evolve CRM API", lifespan=lifespan)

for module in (auth, companies, contacts, deals):
    app.include_router(module.router)


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

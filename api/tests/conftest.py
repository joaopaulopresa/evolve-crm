"""Test fixtures: a real PostgreSQL database, migrated with Alembic, rolled back after each test."""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth import create_token, hash_password
from app.config import get_settings
from app.db import get_session
from app.main import app
from app.models import User

TEST_DATABASE = "crm_test"


@pytest.fixture(scope="session")
def engine():
    base_url = make_url(get_settings().database_url)
    admin_engine = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE} WITH (FORCE)"))
        connection.execute(text(f"CREATE DATABASE {TEST_DATABASE}"))
    admin_engine.dispose()

    test_url = base_url.set(database=TEST_DATABASE)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", test_url.render_as_string(hide_password=False))
    command.upgrade(config, "head")

    engine = create_engine(test_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setattr(get_settings(), "factory_key", "test-factory-key")
    monkeypatch.setattr(get_settings(), "factory_url", None)
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_user(db: Session, email: str, role: str = "user", name: str | None = None) -> User:
    user = User(
        email=email,
        name=name or email.split("@")[0].title(),
        role=role,
        password_hash=hash_password("secret123"),
    )
    db.add(user)
    db.commit()
    return user


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(user)}"}


@pytest.fixture
def admin(db) -> User:
    return make_user(db, "admin@example.test", role="admin")


@pytest.fixture
def alice(db) -> User:
    return make_user(db, "alice@example.test")


@pytest.fixture
def bob(db) -> User:
    return make_user(db, "bob@example.test")

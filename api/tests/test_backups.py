from datetime import UTC, datetime

from app.main import app
from app.routers.backups import StoredObject, list_objects
from tests.conftest import auth


def at(hour: int) -> datetime:
    return datetime(2026, 11, 12, hour, tzinfo=UTC)


OBJECTS = [
    StoredObject("db/production/20261112T060000Z.dump", 45_000, at(6)),
    StoredObject("git/20261112T060000Z.bundle", 900_000, at(6)),
    StoredObject("releases/before-abc123/db.dump", 46_000, at(9)),
    StoredObject("releases/before-abc123/repo.bundle", 910_000, at(9)),
    StoredObject("db/production/20261112T120000Z.dump", 47_000, at(12)),
    StoredObject("notes.txt", 10, at(13)),
]


def test_admin_sees_backups_newest_first_with_the_last_of_each_kind(client, admin):
    app.dependency_overrides[list_objects] = lambda: OBJECTS

    body = client.get("/api/backups", headers=auth(admin)).json()

    assert [backup["key"] for backup in body["backups"]][:2] == [
        "db/production/20261112T120000Z.dump",
        "releases/before-abc123/db.dump",
    ]
    assert len(body["backups"]) == 5, "files that are not backups are left out"
    assert body["last_database_backup_at"].startswith("2026-11-12T12:00")
    assert body["last_git_backup_at"].startswith("2026-11-12T09:00")
    kept = [backup["key"] for backup in body["backups"] if backup["kept_for_release"]]
    assert kept == ["releases/before-abc123/db.dump", "releases/before-abc123/repo.bundle"]


def test_no_backups_yet(client, admin):
    app.dependency_overrides[list_objects] = lambda: []

    body = client.get("/api/backups", headers=auth(admin)).json()

    assert body == {"last_database_backup_at": None, "last_git_backup_at": None, "backups": []}


def test_sales_users_cannot_list_backups(client, alice):
    app.dependency_overrides[list_objects] = lambda: OBJECTS

    assert client.get("/api/backups", headers=auth(alice)).status_code == 403

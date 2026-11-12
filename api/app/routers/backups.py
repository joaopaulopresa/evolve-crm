"""Lets an admin see which backups exist. Taking and restoring them is the backup service's job."""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from minio import Minio
from pydantic import BaseModel

from app.auth import require_admin
from app.config import get_settings

router = APIRouter(prefix="/api/backups", tags=["backups"], dependencies=[Depends(require_admin)])


@dataclass
class StoredObject:
    key: str
    size: int
    last_modified: datetime


class BackupOut(BaseModel):
    key: str
    kind: str  # "database" or "git"
    kept_for_release: bool
    size: int
    created_at: datetime


class BackupsOut(BaseModel):
    last_database_backup_at: datetime | None
    last_git_backup_at: datetime | None
    backups: list[BackupOut]


def list_objects() -> list[StoredObject]:
    settings = get_settings()
    if not settings.s3_endpoint or not settings.s3_access_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Backup storage is not configured")
    endpoint = urlparse(settings.s3_endpoint)
    client = Minio(
        endpoint.netloc,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        secure=endpoint.scheme == "https",
    )
    try:
        if not client.bucket_exists(settings.s3_bucket):
            return []
        objects = client.list_objects(settings.s3_bucket, recursive=True)
        return [StoredObject(o.object_name, o.size, o.last_modified) for o in objects]
    except Exception as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Backup storage is not reachable: {error}"
        ) from error


def summarise(objects: list[StoredObject]) -> BackupsOut:
    backups = [
        BackupOut(
            key=item.key,
            kind="git" if item.key.endswith(".bundle") else "database",
            kept_for_release=item.key.startswith("releases/"),
            size=item.size,
            created_at=item.last_modified,
        )
        for item in sorted(objects, key=lambda item: item.last_modified, reverse=True)
        if item.key.endswith((".dump", ".bundle"))
    ]

    def newest(kind: str) -> datetime | None:
        return next((backup.created_at for backup in backups if backup.kind == kind), None)

    return BackupsOut(
        last_database_backup_at=newest("database"),
        last_git_backup_at=newest("git"),
        backups=backups[:100],
    )


@router.get("", response_model=BackupsOut)
def backups(objects: list[StoredObject] = Depends(list_objects)):
    return summarise(objects)

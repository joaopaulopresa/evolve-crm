"""Client for the deployer, the service that builds, previews, deploys and rolls back."""

import httpx2 as httpx
from fastapi import HTTPException, status

from app.config import get_settings


class Factory:
    def __init__(self, url: str, key: str):
        self.client = httpx.Client(base_url=url, headers={"X-Factory-Key": key}, timeout=15)

    def call(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, f"The deployer is not reachable: {error}"
            ) from error
        if response.status_code >= 400:
            detail = response.json().get("detail", response.text)
            raise HTTPException(response.status_code, detail)
        return response.json()

    def merge(self, change_request_id: int, sha: str) -> None:
        self.call("POST", f"/change-requests/{change_request_id}/merge", json={"sha": sha})

    def discard(self, change_request_id: int) -> None:
        self.call("POST", f"/change-requests/{change_request_id}/discard")

    def rollback(self, requested_by: str) -> dict:
        return self.call("POST", "/rollback", json={"requested_by": requested_by})

    def releases(self) -> dict:
        return self.call("GET", "/releases")


def get_factory() -> Factory:
    settings = get_settings()
    if not settings.factory_url or not settings.factory_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "This environment is not connected to the factory stack, so it cannot change itself. "
            "Use the production environment.",
        )
    return Factory(settings.factory_url, settings.factory_key)

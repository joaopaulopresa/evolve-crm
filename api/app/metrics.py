"""Prometheus metrics, served at /metrics.

The path is outside /api on purpose: the web proxy only forwards /api, so metrics are reachable
from the monitoring network and not from the internet.

Two kinds of numbers:
- traffic (requests, latency), counted by a middleware as requests happen;
- business and delivery numbers (deals per stage, change requests per status, pipeline events,
  time of the last backup), read from the database each time Prometheus scrapes.
"""

import time
from collections.abc import Iterator

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from prometheus_client.core import REGISTRY, CounterMetricFamily, GaugeMetricFamily
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import (
    CHANGE_REQUEST_STATUSES,
    DEAL_STAGES,
    ChangeRequest,
    ChangeRequestEvent,
    Deal,
)

REQUESTS = Counter(
    "evolve_http_requests_total", "HTTP requests handled", ["method", "route", "status"]
)
DURATION = Histogram(
    "evolve_http_request_duration_seconds", "Time spent handling a request", ["method", "route"]
)
BACKUP_CACHE_SECONDS = 60
_backup_cache: tuple[float, float | None] = (0.0, None)


def last_backup_timestamp() -> float | None:
    """Unix time of the newest database backup, or None when storage cannot be read."""
    global _backup_cache
    checked_at, value = _backup_cache
    if time.time() - checked_at < BACKUP_CACHE_SECONDS:
        return value
    try:
        from app.routers.backups import list_objects, summarise

        newest = summarise(list_objects()).last_database_backup_at
        value = newest.timestamp() if newest else None
    except Exception:
        value = None
    _backup_cache = (time.time(), value)
    return value


PIPELINE_KINDS = ("checks_failed", "preview_ready", "deployed", "deploy_failed", "rolled_back")


class BusinessCollector:
    """Reads its numbers from the database when scraped. The session is set per request."""

    session: Session | None = None

    def collect(self) -> Iterator:
        if self.session is None:
            return
        session = self.session

        deals = GaugeMetricFamily("evolve_deals", "Deals by pipeline stage", labels=["stage"])
        by_stage = dict(
            session.execute(select(Deal.stage, func.count()).group_by(Deal.stage)).all()
        )
        for stage in DEAL_STAGES:
            deals.add_metric([stage], by_stage.get(stage, 0))
        yield deals

        created = CounterMetricFamily("evolve_deals_created", "Deals ever created")
        created.add_metric([], session.scalar(select(func.coalesce(func.max(Deal.id), 0))))
        yield created

        requests = GaugeMetricFamily(
            "evolve_change_requests", "Change requests by status", labels=["status"]
        )
        by_status = dict(
            session.execute(
                select(ChangeRequest.status, func.count()).group_by(ChangeRequest.status)
            ).all()
        )
        for status in CHANGE_REQUEST_STATUSES:
            requests.add_metric([status], by_status.get(status, 0))
        yield requests

        events = CounterMetricFamily(
            "evolve_pipeline_events", "Delivery pipeline events", labels=["kind"]
        )
        by_kind = dict(
            session.execute(
                select(ChangeRequestEvent.kind, func.count())
                .where(ChangeRequestEvent.actor == "pipeline")
                .group_by(ChangeRequestEvent.kind)
            ).all()
        )
        for kind in PIPELINE_KINDS:
            events.add_metric([kind], by_kind.get(kind, 0))
        yield events

        backup = last_backup_timestamp()
        if backup is not None:
            yield GaugeMetricFamily(
                "backup_last_success_timestamp",
                "Unix time of the newest database backup in storage",
                value=backup,
            )


collector = BusinessCollector()
REGISTRY.register(collector)


def route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", "unmatched")


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def measure(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        route = route_template(request)
        if route != "/metrics":
            REQUESTS.labels(request.method, route, str(response.status_code)).inc()
            DURATION.labels(request.method, route).observe(time.perf_counter() - started)
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request) -> Response:
        # Resolve the session the same way endpoints do, so tests can substitute theirs.
        provider = request.app.dependency_overrides.get(get_session, get_session)
        sessions = provider()
        managed = hasattr(sessions, "__next__")
        collector.session = next(sessions) if managed else sessions
        try:
            return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
        finally:
            collector.session = None
            if managed:
                sessions.close()

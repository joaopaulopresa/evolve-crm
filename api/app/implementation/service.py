"""The life of a change request: who may move it between states, and what gets recorded."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.implementation.schemas import PipelineEvent
from app.models import ChangeRequest, ChangeRequestEvent, User

# Pipeline event -> the status it puts the request in (None keeps the current status).
PIPELINE_STATUS = {
    "checks_started": "checking",
    "checks_passed": None,
    "checks_failed": "checks_failed",
    "preview_failed": "checks_failed",
    "preview_ready": "preview_ready",
    "preview_removed": None,
    "merge_failed": "preview_ready",
    "deploy_started": "deploying",
    "deployed": "live",
    "deploy_failed": "deploy_failed",
    "rolled_back": "rolled_back",
    "rollback_failed": None,
}

MESSAGES = {
    "checks_started": "Checks started: protected paths, migration safety, lint and tests.",
    "checks_passed": "All checks passed. Building the preview.",
    "checks_failed": "Checks failed. Nothing was deployed.",
    "preview_failed": "The preview could not be started.",
    "preview_ready": "The preview is ready to try.",
    "preview_removed": "The preview was removed.",
    "merge_failed": "The change could not be merged into main.",
    "deploy_started": "Deploying to production.",
    "deployed": "Live in production.",
    "deploy_failed": "The production deploy failed; the previous release was restored.",
    "rolled_back": "Production was rolled back to the previous release.",
    "rollback_failed": "The rollback failed.",
}


def record(
    session: Session,
    request: ChangeRequest | None,
    kind: str,
    actor: str,
    message: str | None = None,
    log: str | None = None,
    data: dict | None = None,
) -> ChangeRequestEvent:
    event = ChangeRequestEvent(
        change_request_id=request.id if request else None,
        kind=kind,
        actor=actor,
        message=message,
        log=log,
        data=data,
    )
    session.add(event)
    return event


def open_request(session: Session, description: str, user: User) -> ChangeRequest:
    title = description.strip().splitlines()[0][:120]
    request = ChangeRequest(title=title, description=description.strip(), requested_by=user)
    session.add(request)
    session.flush()
    request.branch = f"cr/{request.id}"
    record(session, request, "opened", user.email, description.strip())
    return request


def apply_pipeline_event(session: Session, event: PipelineEvent) -> None:
    request = (
        session.get(ChangeRequest, event.change_request_id) if event.change_request_id else None
    )
    extra = {key: value for key, value in (event.model_extra or {}).items() if value is not None}
    data = {"sha": event.sha, "url": event.url, **extra}
    record(
        session,
        request,
        event.kind,
        "pipeline",
        MESSAGES.get(event.kind),
        event.log,
        {key: value for key, value in data.items() if value is not None},
    )
    if request is None or request.status == "discarded":
        return

    if event.kind == "checks_started":
        # A new commit is under review: whatever was approved before no longer counts.
        request.head_sha = event.sha
        request.approved_sha = None
        request.approved_by = None
        request.branch = event.branch or request.branch
    if event.kind == "preview_ready":
        request.head_sha = event.sha
        request.preview_url = event.url
    if event.kind in ("deployed", "preview_removed"):
        request.preview_url = None

    new_status = PIPELINE_STATUS.get(event.kind)
    if new_status:
        request.status = new_status


def approve(session: Session, request: ChangeRequest, user: User) -> None:
    if request.status != "preview_ready" or not request.head_sha:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only a change with a ready preview can be approved"
        )
    request.status = "approved"
    request.approved_by = user
    request.approved_sha = request.head_sha
    record(session, request, "approved", user.email, data={"sha": request.head_sha})


def discard(session: Session, request: ChangeRequest, user: User) -> None:
    if request.status in ("approved", "deploying", "live", "rolled_back", "discarded"):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"A change that is {request.status} cannot be discarded"
        )
    request.status = "discarded"
    request.preview_url = None
    record(session, request, "discarded", user.email)


def is_approved(request: ChangeRequest | None, sha: str) -> bool:
    return bool(request and request.status == "approved" and request.approved_sha == sha)

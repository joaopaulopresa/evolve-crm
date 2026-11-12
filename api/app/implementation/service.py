"""The life of a change request: who may move it between states, and what gets recorded."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.implementation.schemas import PipelineEvent
from app.models import CHANGE_REQUEST_FINAL, ChangeRequest, ChangeRequestEvent, User

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


# After checks fail, the agent gets the log and one more go before the owner is asked.
AUTOMATIC_FIX_ATTEMPTS = 1
LOG_FOR_AGENT = 4000  # characters from the end of the checks log


def unfinished_request(session: Session) -> ChangeRequest | None:
    return session.scalar(
        select(ChangeRequest).where(ChangeRequest.status.not_in(CHANGE_REQUEST_FINAL)).limit(1)
    )


def open_request(session: Session, description: str, user: User, with_agent: bool) -> ChangeRequest:
    """with_agent=False opens a request for a branch a developer pushes by hand."""
    other = unfinished_request(session)
    if other is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Change request #{other.id} is still in progress. Finish or discard it first.",
        )
    text = description.strip()
    request = ChangeRequest(title=text.splitlines()[0][:120], description=text, requested_by=user)
    if with_agent:
        request.status = "queued"
        request.pending_message = text
    session.add(request)
    session.flush()
    request.branch = f"cr/{request.id}"
    record(session, request, "opened", user.email, text)
    return request


REPLY_ALLOWED = ("needs_input", "checks_failed", "preview_ready")


def reply(session: Session, request: ChangeRequest, text: str, user: User) -> None:
    """The owner answers a question or asks for an adjustment; the agent continues."""
    if request.status not in REPLY_ALLOWED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"A change that is {request.status} cannot take a reply now"
        )
    request.status = "queued"
    request.pending_message = text.strip()
    request.approved_sha = None
    record(session, request, "message", user.email, text.strip())


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

    if (
        event.kind == "checks_failed"
        and request.agent_session_id
        and request.agent_attempts <= AUTOMATIC_FIX_ATTEMPTS
    ):
        request.status = "queued"
        request.pending_message = (
            "The pipeline rejected the branch you submitted. Fix the cause and submit again. "
            f"End of the checks log:\n{(event.log or '')[-LOG_FOR_AGENT:]}"
        )
        record(
            session, request, "agent_retry", "pipeline", "Sent the failed checks back to Hermes."
        )


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
    if request.status in ("working", "approved", "deploying", *CHANGE_REQUEST_FINAL):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"A change that is {request.status} cannot be discarded"
        )
    request.status = "discarded"
    request.preview_url = None
    record(session, request, "discarded", user.email)


def is_approved(request: ChangeRequest | None, sha: str) -> bool:
    return bool(request and request.status == "approved" and request.approved_sha == sha)

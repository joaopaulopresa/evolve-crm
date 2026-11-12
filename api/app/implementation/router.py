import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.config import get_settings
from app.db import get_session
from app.implementation import service
from app.implementation.factory import Factory, get_factory
from app.implementation.schemas import (
    ChangeRequestDetail,
    ChangeRequestIn,
    ChangeRequestOut,
    EventOut,
    PipelineEvent,
)
from app.models import ChangeRequest, ChangeRequestEvent, User

router = APIRouter(prefix="/api", tags=["change requests"])


def to_out(request: ChangeRequest, detail: bool = False) -> dict:
    columns = {
        column.name: getattr(request, column.name) for column in ChangeRequest.__table__.columns
    }
    out = {
        **columns,
        "requested_by_name": request.requested_by.name,
        "approved_by_name": request.approved_by.name if request.approved_by else None,
    }
    if detail:
        out["events"] = request.events
    return out


def get_request(change_request_id: int, session: Session = Depends(get_session)) -> ChangeRequest:
    request = session.get(ChangeRequest, change_request_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Change request not found")
    return request


# --- for admins, from the Implement page ------------------------------------------------------


@router.post("/change-requests", response_model=ChangeRequestOut, status_code=201)
def open_change_request(
    payload: ChangeRequestIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
    _: Factory = Depends(get_factory),
):
    request = service.open_request(session, payload.description, user)
    session.commit()
    return to_out(request)


@router.get("/change-requests", response_model=list[ChangeRequestOut])
def list_change_requests(session: Session = Depends(get_session), _: User = Depends(require_admin)):
    requests = session.scalars(select(ChangeRequest).order_by(ChangeRequest.id.desc())).all()
    return [to_out(request) for request in requests]


@router.get("/change-requests/{change_request_id}", response_model=ChangeRequestDetail)
def read_change_request(
    request: ChangeRequest = Depends(get_request), _: User = Depends(require_admin)
):
    return to_out(request, detail=True)


@router.post("/change-requests/{change_request_id}/approve", response_model=ChangeRequestOut)
def approve_change_request(
    request: ChangeRequest = Depends(get_request),
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
    factory: Factory = Depends(get_factory),
):
    service.approve(session, request, user)
    # Commit first: the git hook asks this API whether the commit is approved.
    session.commit()
    factory.merge(request.id, request.approved_sha)
    return to_out(request)


@router.post("/change-requests/{change_request_id}/discard", response_model=ChangeRequestOut)
def discard_change_request(
    request: ChangeRequest = Depends(get_request),
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
    factory: Factory = Depends(get_factory),
):
    service.discard(session, request, user)
    session.commit()
    factory.discard(request.id)
    return to_out(request)


@router.get("/releases")
def releases(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
    factory: Factory = Depends(get_factory),
):
    events = session.scalars(
        select(ChangeRequestEvent)
        .where(ChangeRequestEvent.actor == "pipeline")
        .where(ChangeRequestEvent.kind.in_(("deployed", "deploy_failed", "rolled_back")))
        .order_by(ChangeRequestEvent.id.desc())
        .limit(30)
    ).all()
    return {
        **factory.releases(),
        "events": [
            EventOut.model_validate(event).model_dump()
            | {"change_request_id": event.change_request_id}
            for event in events
        ],
    }


@router.post("/releases/rollback", status_code=status.HTTP_202_ACCEPTED)
def rollback(
    session: Session = Depends(get_session),
    user: User = Depends(require_admin),
    factory: Factory = Depends(get_factory),
):
    result = factory.rollback(user.email)
    service.record(session, None, "rollback_requested", user.email, data=result)
    session.commit()
    return result


# --- for the deployer -------------------------------------------------------------------------


def factory_key(x_factory_key: str = Header(default="")) -> None:
    expected = get_settings().factory_key
    if not expected or not secrets.compare_digest(x_factory_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong factory key")


internal = APIRouter(
    prefix="/api/internal", dependencies=[Depends(factory_key)], include_in_schema=False
)


@internal.post("/pipeline-events", status_code=status.HTTP_204_NO_CONTENT)
def pipeline_event(event: PipelineEvent, session: Session = Depends(get_session)):
    service.apply_pipeline_event(session, event)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@internal.get("/change-requests/{change_request_id}/approval")
def approval(change_request_id: int, sha: str, session: Session = Depends(get_session)):
    return {"approved": service.is_approved(session.get(ChangeRequest, change_request_id), sha)}

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_session
from app.models import OPEN_STAGES, Deal, User
from app.schemas import DealIn, DealOut, DealPatch
from app.visibility import visible_deals

router = APIRouter(prefix="/api/deals", tags=["deals"])


def to_out(deal: Deal) -> DealOut:
    contact = deal.contact
    return DealOut.model_validate(
        {
            **{column.name: getattr(deal, column.name) for column in Deal.__table__.columns},
            "company_name": deal.company.name if deal.company else None,
            "contact_name": f"{contact.first_name} {contact.last_name}" if contact else None,
            "owner_name": deal.owner.name,
        }
    )


def get_deal(
    deal_id: int, session: Session = Depends(get_session), user: User = Depends(current_user)
) -> Deal:
    deal = session.scalar(visible_deals(select(Deal).where(Deal.id == deal_id), user))
    if deal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deal not found")
    return deal


def apply_stage(deal: Deal, stage: str) -> None:
    """Closing a deal stamps closed_at; reopening it clears the stamp."""
    if stage in OPEN_STAGES:
        deal.closed_at = None
    elif deal.stage in OPEN_STAGES or deal.closed_at is None:
        deal.closed_at = datetime.now(UTC)
    deal.stage = stage


@router.get("", response_model=list[DealOut])
def list_deals(
    stage: str | None = None,
    owner_id: int | None = None,
    q: str | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    query = visible_deals(select(Deal), user).order_by(Deal.created_at.desc(), Deal.id.desc())
    if stage:
        query = query.where(Deal.stage == stage)
    if owner_id:
        query = query.where(Deal.owner_id == owner_id)
    if q:
        query = query.where(Deal.title.ilike(f"%{q}%"))
    return [to_out(deal) for deal in session.scalars(query).all()]


@router.post("", response_model=DealOut, status_code=status.HTTP_201_CREATED)
def create_deal(
    payload: DealIn, session: Session = Depends(get_session), user: User = Depends(current_user)
):
    data = payload.model_dump(exclude={"stage", "owner_id"})
    owner_id = payload.owner_id if user.role == "admin" and payload.owner_id else user.id
    deal = Deal(**data, owner_id=owner_id, stage="lead")
    apply_stage(deal, payload.stage)
    session.add(deal)
    session.commit()
    session.refresh(deal)
    return to_out(deal)


@router.get("/{deal_id}", response_model=DealOut)
def read_deal(deal: Deal = Depends(get_deal)):
    return to_out(deal)


@router.patch("/{deal_id}", response_model=DealOut)
def update_deal(
    payload: DealPatch,
    deal: Deal = Depends(get_deal),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    changes = payload.model_dump(exclude_unset=True)
    if "owner_id" in changes and changes["owner_id"] != deal.owner_id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an admin can reassign a deal")
    stage = changes.pop("stage", None)
    for field, value in changes.items():
        setattr(deal, field, value)
    if stage:
        apply_stage(deal, stage)
    session.commit()
    session.refresh(deal)
    return to_out(deal)


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deal(deal: Deal = Depends(get_deal), session: Session = Depends(get_session)):
    session.delete(deal)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

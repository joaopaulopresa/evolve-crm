from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_session
from app.models import Activity, User
from app.schemas import ActivityIn, ActivityOut, ActivityPatch
from app.visibility import visible_activities

router = APIRouter(prefix="/api/activities", tags=["activities"])


def to_out(activity: Activity) -> ActivityOut:
    return ActivityOut.model_validate(
        {
            **{
                column.name: getattr(activity, column.name) for column in Activity.__table__.columns
            },
            "owner_name": activity.owner.name,
        }
    )


def overdue_tasks(query: Select) -> Select:
    return query.where(
        Activity.type == "task",
        Activity.completed_at.is_(None),
        Activity.due_date < date.today(),
    )


def get_activity(
    activity_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> Activity:
    query = visible_activities(select(Activity).where(Activity.id == activity_id), user)
    activity = session.scalar(query)
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    return activity


@router.get("", response_model=list[ActivityOut])
def list_activities(
    contact_id: int | None = None,
    deal_id: int | None = None,
    type: str | None = None,
    overdue: bool = False,
    limit: int = 200,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    query = visible_activities(select(Activity), user)
    if contact_id:
        query = query.where(Activity.contact_id == contact_id)
    if deal_id:
        query = query.where(Activity.deal_id == deal_id)
    if type:
        query = query.where(Activity.type == type)
    if overdue:
        query = overdue_tasks(query)
    query = query.order_by(Activity.occurred_at.desc(), Activity.id.desc()).limit(limit)
    return [to_out(activity) for activity in session.scalars(query).all()]


@router.post("", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
def create_activity(
    payload: ActivityIn,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    data = payload.model_dump(exclude_none=True)
    activity = Activity(**data, owner_id=user.id)
    session.add(activity)
    session.commit()
    session.refresh(activity)
    return to_out(activity)


@router.patch("/{activity_id}", response_model=ActivityOut)
def update_activity(
    payload: ActivityPatch,
    activity: Activity = Depends(get_activity),
    session: Session = Depends(get_session),
):
    changes = payload.model_dump(exclude_unset=True)
    completed = changes.pop("completed", None)
    for field, value in changes.items():
        setattr(activity, field, value)
    if completed is not None:
        activity.completed_at = datetime.now(UTC) if completed else None
    session.commit()
    session.refresh(activity)
    return to_out(activity)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(
    activity: Activity = Depends(get_activity), session: Session = Depends(get_session)
):
    session.delete(activity)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

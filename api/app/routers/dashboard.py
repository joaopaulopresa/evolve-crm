from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_user
from app.db import get_session
from app.models import OPEN_STAGES, Activity, Deal, User
from app.routers.activities import overdue_tasks, to_out
from app.schemas import DashboardOut
from app.visibility import visible_activities, visible_deals

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(session: Session = Depends(get_session), user: User = Depends(current_user)):
    totals = select(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.value), 0))
    by_stage = {
        stage: (count, value)
        for stage, count, value in session.execute(
            visible_deals(totals, user).where(Deal.stage.in_(OPEN_STAGES)).group_by(Deal.stage)
        )
    }
    pipeline = [
        {
            "stage": stage,
            "count": by_stage.get(stage, (0, 0))[0],
            "value": by_stage.get(stage, (0, 0))[1],
        }
        for stage in OPEN_STAGES
    ]

    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    won = select(func.count(Deal.id), func.coalesce(func.sum(Deal.value), 0)).where(
        Deal.stage == "won", Deal.closed_at >= month_start
    )
    won_count, won_value = session.execute(visible_deals(won, user)).one()

    tasks = overdue_tasks(visible_activities(select(Activity), user)).order_by(Activity.due_date)

    return {
        "pipeline": pipeline,
        "won_this_month": {"count": won_count, "value": won_value},
        "overdue_tasks": [to_out(task) for task in session.scalars(tasks.limit(20)).all()],
    }

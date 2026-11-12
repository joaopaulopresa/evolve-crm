from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChangeRequestIn(BaseModel):
    description: str = Field(min_length=3, max_length=4000)
    # True when a developer will push the branch by hand instead of asking the agent.
    manual: bool = False


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    actor: str
    message: str | None
    log: str | None
    data: dict | None
    created_at: datetime


class ChangeRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: str
    branch: str | None
    head_sha: str | None
    preview_url: str | None
    summary: str | None
    tokens: int
    cost_usd: float | None
    trace_url: str | None
    requested_by_name: str
    approved_by_name: str | None
    created_at: datetime
    updated_at: datetime


class ChangeRequestDetail(ChangeRequestOut):
    events: list[EventOut]


class PipelineEvent(BaseModel):
    """Sent by the deployer. Extra fields are kept in the event's data."""

    model_config = ConfigDict(extra="allow")

    kind: str
    change_request_id: int | None = None
    sha: str | None = None
    branch: str | None = None
    url: str | None = None
    log: str | None = None

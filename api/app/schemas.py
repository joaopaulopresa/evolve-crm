"""Request and response shapes. `*In` is what clients send, `*Out` is what the API returns."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal["admin", "user"]
Stage = Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"]
ActivityType = Literal["note", "call", "meeting", "task"]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- users and auth ---------------------------------------------------------------------------


class UserOut(Out):
    id: int
    email: str
    name: str
    role: Role


class UserIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8)
    role: Role = "user"


class LoginIn(BaseModel):
    email: str
    password: str


class LoginOut(BaseModel):
    access_token: str
    user: UserOut


# --- companies --------------------------------------------------------------------------------


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    industry: str | None = None
    website: str | None = None
    city: str | None = None
    country: str | None = None


class CompanyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    industry: str | None = None
    website: str | None = None
    city: str | None = None
    country: str | None = None


class CompanyOut(Out):
    id: int
    name: str
    industry: str | None
    website: str | None
    city: str | None
    country: str | None
    created_at: datetime


# --- contacts ---------------------------------------------------------------------------------


class ContactIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: str | None = None
    phone: str | None = None
    job_title: str | None = None
    company_id: int | None = None


class ContactPatch(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    email: str | None = None
    phone: str | None = None
    job_title: str | None = None
    company_id: int | None = None


class ContactOut(Out):
    id: int
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    job_title: str | None
    company_id: int | None
    company_name: str | None
    created_at: datetime


# --- deals ------------------------------------------------------------------------------------


class DealIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    value: float = Field(default=0, ge=0)
    stage: Stage = "lead"
    company_id: int | None = None
    contact_id: int | None = None
    owner_id: int | None = None
    expected_close_date: date | None = None


class DealPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    value: float | None = Field(default=None, ge=0)
    stage: Stage | None = None
    company_id: int | None = None
    contact_id: int | None = None
    owner_id: int | None = None
    expected_close_date: date | None = None


class DealOut(Out):
    id: int
    title: str
    value: float
    stage: Stage
    company_id: int | None
    company_name: str | None
    contact_id: int | None
    contact_name: str | None
    owner_id: int
    owner_name: str
    expected_close_date: date | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


# --- activities -------------------------------------------------------------------------------


class ActivityIn(BaseModel):
    type: ActivityType
    subject: str = Field(min_length=1, max_length=200)
    body: str | None = None
    contact_id: int | None = None
    deal_id: int | None = None
    occurred_at: datetime | None = None
    due_date: date | None = None

    @model_validator(mode="after")
    def attached_to_something(self):
        if self.contact_id is None and self.deal_id is None:
            raise ValueError("An activity must belong to a contact or a deal")
        return self


class ActivityPatch(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None
    due_date: date | None = None
    completed: bool | None = None


class ActivityOut(Out):
    id: int
    type: ActivityType
    subject: str
    body: str | None
    contact_id: int | None
    deal_id: int | None
    owner_id: int
    owner_name: str
    occurred_at: datetime
    due_date: date | None
    completed_at: datetime | None


# --- dashboard --------------------------------------------------------------------------------


class StageSummary(BaseModel):
    stage: Stage
    count: int
    value: float


class WonSummary(BaseModel):
    count: int
    value: float


class DashboardOut(BaseModel):
    pipeline: list[StageSummary]
    won_this_month: WonSummary
    overdue_tasks: list[ActivityOut]

"""Database tables. One class per table; add columns here and create an Alembic migration."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

ROLES = ("admin", "user")
DEAL_STAGES = ("lead", "qualified", "proposal", "negotiation", "won", "lost")
OPEN_STAGES = ("lead", "qualified", "proposal", "negotiation")
ACTIVITY_TYPES = ("note", "call", "meeting", "task")
CHANGE_REQUEST_STATUSES = (
    "open",  # created without an agent (a developer pushes the branch by hand)
    "queued",  # waiting for the agent to pick up the request or the owner's reply
    "working",  # the agent is implementing it
    "needs_input",  # the agent asked a question, declined or got stuck; the owner replies
    "checking",  # the branch was pushed; checks and the preview build are running
    "checks_failed",
    "preview_ready",  # waiting for an admin to try the preview and approve or discard
    "approved",  # approved; the merge and the production deploy follow
    "deploying",
    "live",
    "deploy_failed",  # production was restored to the previous release
    "rolled_back",
    "discarded",
)
# A request in one of these is finished. Only one unfinished request exists at a time.
CHANGE_REQUEST_FINAL = ("live", "deploy_failed", "rolled_back", "discarded")


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    industry: Mapped[str | None] = mapped_column(String(80))
    website: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    job_title: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company | None] = relationship(back_populates="contacts")


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    stage: Mapped[str] = mapped_column(String(20), default="lead", index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    expected_close_date: Mapped[date | None] = mapped_column(Date)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company | None] = relationship()
    contact: Mapped[Contact | None] = relationship()
    owner: Mapped[User] = relationship()


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    deal_id: Mapped[int | None] = mapped_column(
        ForeignKey("deals.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship()


class ChangeRequest(Base):
    """A change to the product itself, asked for in the Implement page."""

    __tablename__ = "change_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    branch: Mapped[str | None] = mapped_column(String(120))
    head_sha: Mapped[str | None] = mapped_column(String(40))
    approved_sha: Mapped[str | None] = mapped_column(String(40))
    preview_url: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    agent_session_id: Mapped[str | None] = mapped_column(String(120))
    pending_message: Mapped[str | None] = mapped_column(Text)
    agent_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    tokens: Mapped[int] = mapped_column(default=0, server_default="0")
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    trace_url: Mapped[str | None] = mapped_column(String(255))
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    requested_by: Mapped[User] = relationship(foreign_keys=[requested_by_id])
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_id])
    events: Mapped[list["ChangeRequestEvent"]] = relationship(
        back_populates="change_request", order_by="ChangeRequestEvent.id"
    )


class ChangeRequestEvent(Base):
    """Everything that happened to a change request: chat, agent progress, pipeline, decisions.

    Rows without a change request are pipeline events of the installation itself (first deploy,
    operator pushes). Together they are the audit log of delivery.
    """

    __tablename__ = "change_request_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    change_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("change_requests.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(120))
    message: Mapped[str | None] = mapped_column(Text)
    log: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    change_request: Mapped[ChangeRequest | None] = relationship(back_populates="events")

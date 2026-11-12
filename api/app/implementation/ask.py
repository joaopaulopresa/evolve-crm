"""Ask: questions about the CRM's data, answered by the analyst agent.

The analyst can only call the read-only crm-data tools. Before each question this module
tells the crm-data server which CRM user is asking; the database then filters the rows (see
the reader-role migration). The model never chooses whose data it reads.
"""

import secrets
import threading

import httpx2 as httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import current_user
from app.config import get_settings
from app.implementation.agent import Finished, Hermes
from app.models import User

router = APIRouter(prefix="/api/ask", tags=["ask"])

# The crm-data server acts for one user at a time, so questions are answered one by one.
one_at_a_time = threading.Lock()
QUESTION_SECONDS = 180


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    conversation_id: str | None = None


class QueryOut(BaseModel):
    sql: str
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0
    truncated: bool = False
    error: str | None = None


class AskOut(BaseModel):
    answer: str
    queries: list[QueryOut]
    conversation_id: str


class CrmData:
    """Sets and clears who the crm-data tools act for."""

    def __init__(self, url: str, key: str):
        self.client = httpx.Client(base_url=url, headers={"X-Context-Key": key}, timeout=10)

    def begin(self, user: User) -> None:
        self.client.post(
            "/context",
            json={"user_id": user.id, "role": user.role, "ttl_seconds": QUESTION_SECONDS},
        ).raise_for_status()

    def end(self) -> list[dict]:
        response = self.client.delete("/context")
        response.raise_for_status()
        return response.json()["queries"]


def unavailable(reason: str) -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, reason)


def get_analyst() -> Hermes:
    settings = get_settings()
    if not settings.ask_enabled:
        raise unavailable("Questions about the data are switched off for this installation.")
    if not (settings.hermes_analyst_url and settings.hermes_analyst_key):
        raise unavailable("This environment is not connected to the analyst agent.")
    return Hermes(settings.hermes_analyst_url, settings.hermes_analyst_key)


def get_crm_data() -> CrmData:
    settings = get_settings()
    if not (settings.crm_data_url and settings.crm_data_context_key):
        raise unavailable("This environment is not connected to the data tools.")
    return CrmData(settings.crm_data_url, settings.crm_data_context_key)


def conversation_for(user: User, conversation_id: str | None) -> str:
    """A conversation belongs to the user who started it. Its id starts with their user id, so
    nobody can continue (and so read back) someone else's conversation."""
    prefix = f"ask-{user.id}-"
    if conversation_id and conversation_id.startswith(prefix):
        return conversation_id
    return prefix + secrets.token_hex(6)


@router.post("", response_model=AskOut)
def ask(
    payload: AskIn,
    user: User = Depends(current_user),
    analyst: Hermes = Depends(get_analyst),
    crm_data: CrmData = Depends(get_crm_data),
):
    conversation_id = conversation_for(user, payload.conversation_id)
    if not one_at_a_time.acquire(timeout=QUESTION_SECONDS):
        raise unavailable("The analyst is busy with other questions. Try again in a moment.")
    try:
        crm_data.begin(user)
        try:
            finished = Finished(False, "The analyst stopped without an answer.")
            for item in analyst.run(payload.question, conversation_id):
                if isinstance(item, Finished):
                    finished = item
        finally:
            queries = crm_data.end()
    except httpx.HTTPError as error:
        raise unavailable(f"The analyst could not be reached: {error}") from error
    finally:
        one_at_a_time.release()

    if not finished.ok:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"The analyst failed: {finished.output}")
    return {
        "answer": finished.output.strip(),
        "queries": queries,
        "conversation_id": conversation_id,
    }

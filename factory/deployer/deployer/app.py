"""HTTP front of the deployer.

Callers: the git hooks (may main move? something was pushed) and the CRM API (roll back,
discard a preview, list releases). Work is queued and done one job at a time; results go back
to the CRM as pipeline events.
"""

import logging
import os
import queue
import subprocess
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx2 as httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from deployer.config import Config
from deployer.pipeline import Pipeline
from deployer.state import State

log = logging.getLogger("deployer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

config = Config()
LOG_TAIL = 12_000  # characters of script output kept for the CRM


def run_script(scripts: Path, script: str, args: list[str]) -> tuple[int, str]:
    log.info("run %s %s", script, " ".join(args))
    process = subprocess.run(
        [str(scripts / script), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "GIT_DIR": str(config.git_dir)},
    )
    log.info("%s exited %s\n%s", script, process.returncode, process.stdout[-2000:])
    return process.returncode, process.stdout[-LOG_TAIL:]


def crm(method: str, path: str, **kwargs) -> httpx.Response:
    return httpx.request(
        method,
        f"{config.crm_url}{path}",
        headers={"X-Factory-Key": config.factory_key},
        timeout=10,
        **kwargs,
    )


def report(kind: str, fields: dict) -> None:
    """Tell the CRM. It may be down (it is, during its own first deploy): that is not an error."""
    log.info("event %s %s", kind, {k: v for k, v in fields.items() if k != "log"})
    try:
        crm("POST", "/api/internal/pipeline-events", json={"kind": kind, **fields})
    except httpx.HTTPError as error:
        log.warning("could not report %s to the CRM: %s", kind, error)


def approved(change_request_id: int, sha: str) -> bool:
    try:
        response = crm(
            "GET",
            f"/api/internal/change-requests/{change_request_id}/approval",
            params={"sha": sha},
        )
        return response.status_code == 200 and response.json().get("approved") is True
    except httpx.HTTPError:
        return False


pipeline = Pipeline(config, State(config.state_dir), run_script, report)
jobs: queue.Queue[Callable[[], None]] = queue.Queue()


def worker() -> None:
    while True:
        job = jobs.get()
        try:
            job()
        except Exception:
            log.exception("job failed")
        finally:
            jobs.task_done()


@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=worker, daemon=True).start()
    yield


def factory_key(x_factory_key: str = Header(default="")) -> None:
    if not config.factory_key or x_factory_key != config.factory_key:
        raise HTTPException(401, "Wrong factory key")


app = FastAPI(title="Evolve CRM deployer", lifespan=lifespan, dependencies=[Depends(factory_key)])


class Push(BaseModel):
    ref: str
    old: str
    new: str


class Merge(BaseModel):
    sha: str


class Rollback(BaseModel):
    requested_by: str | None = None


@app.get("/hooks/can-merge")
def can_merge(sha: str) -> dict:
    allowed, reason = pipeline.can_merge(sha, approved)
    return {"allowed": allowed, "reason": reason}


@app.post("/hooks/pushed", status_code=202)
def pushed(push: Push) -> dict:
    jobs.put(lambda: pipeline.pushed(push.ref, push.old, push.new))
    return {"queued": True}


@app.get("/releases")
def releases() -> dict:
    state = pipeline.state
    return {
        "current": state.current,
        "rollback_target": state.rollback_target,
        "history": state.releases[-50:],
        "busy": jobs.unfinished_tasks > 0,
    }


@app.post("/rollback", status_code=202)
def rollback(body: Rollback) -> dict:
    if pipeline.state.rollback_target is None:
        raise HTTPException(409, "There is no earlier release to roll back to")
    jobs.put(lambda: pipeline.rollback(body.requested_by))
    return {"queued": True, "target": pipeline.state.rollback_target}


@app.post("/change-requests/{change_request_id}/discard", status_code=202)
def discard(change_request_id: int) -> dict:
    jobs.put(lambda: pipeline.discard(change_request_id))
    return {"queued": True}


@app.post("/change-requests/{change_request_id}/merge", status_code=202)
def merge(change_request_id: int, body: Merge) -> dict:
    jobs.put(lambda: pipeline.merge(change_request_id, body.sha))
    return {"queued": True}

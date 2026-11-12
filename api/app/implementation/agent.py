"""Client for Hermes Agent's HTTP API (the Runs API of its gateway).

One function matters to the rest of the app: run(), which starts a run and yields what
happens. Tests replace it with a fake, so the suite needs neither Hermes nor an API key.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass

import httpx2 as httpx

FINAL_EVENTS = {"run.completed", "run.failed", "run.cancelled", "run.interrupted"}


@dataclass
class Step:
    """Something the agent did: used a tool."""

    tool: str
    preview: str


@dataclass
class Finished:
    ok: bool
    output: str  # the agent's reply, or the reason the run failed
    tokens: int = 0


@dataclass
class Usage:
    tokens: int
    cost_usd: float | None


class Hermes:
    def __init__(self, url: str, key: str):
        self.client = httpx.Client(
            base_url=url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(30, read=None),
        )

    def run(self, prompt: str, session_id: str) -> Iterator[Step | Finished]:
        """Start a run in the given session and yield its steps, then how it finished."""
        started = self.client.post("/v1/runs", json={"input": prompt, "session_id": session_id})
        started.raise_for_status()
        run_id = started.json()["run_id"]

        with self.client.stream("GET", f"/v1/runs/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if not line.startswith("data:"):
                    continue  # comments and keep-alives
                event = json.loads(line[5:])
                kind = event.get("event")
                if kind == "tool.started":
                    yield Step(event.get("tool", ""), event.get("preview") or "")
                elif kind == "run.completed":
                    usage = event.get("usage") or {}
                    yield Finished(True, event.get("output") or "", usage.get("total_tokens", 0))
                    return
                elif kind in FINAL_EVENTS:
                    yield Finished(False, event.get("error") or kind)
                    return
        # The stream closed without a final event: ask for the outcome.
        final = self.client.get(f"/v1/runs/{run_id}").json()
        ok = final.get("status") == "completed"
        yield Finished(ok, final.get("output") or final.get("status") or "unknown")

    def usage(self, session_id: str) -> Usage | None:
        """Tokens and estimated cost of a whole session, as Hermes accounts them."""
        try:
            response = self.client.get(f"/api/sessions/{session_id}", timeout=10)
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        data = response.json()
        data = data.get("session", data)
        tokens = (data.get("input_tokens") or 0) + (data.get("output_tokens") or 0)
        cost = data.get("actual_cost_usd") or data.get("estimated_cost_usd")
        return Usage(tokens, cost)

"""MCP server exposing three read-only tools over the CRM database.

Who is asking is never taken from the model. Before it starts a question, the CRM API tells
this server which CRM user the next tool calls are for (POST /context); when the answer is
done it ends the context (DELETE /context) and gets back the queries that ran, so the page
can show the SQL behind the answer. Without an active context every tool refuses.

Two keys, both required:
  CRM_DATA_MCP_KEY      bearer token of the MCP endpoint (/mcp), known to the analyst agent
  CRM_DATA_CONTEXT_KEY  X-Context-Key header of /context, known to the CRM API only
"""

import contextlib
import os
import secrets
import time

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from crm_data import queries
from crm_data.queries import Identity, QueryError

MAX_CONTEXT_SECONDS = 600
KEPT_ROWS = 50  # rows of each result kept for the page; the model receives up to ROW_CAP

mcp = MCPServer(
    "crm-data",
    instructions=(
        "Read-only access to the CRM database for the person asking. Call describe_schema "
        "first, then run_query with one PostgreSQL SELECT. Do the arithmetic in SQL."
    ),
)


class Context:
    """The CRM user the tools currently act for, and what they ran."""

    def __init__(self) -> None:
        self.identity: Identity | None = None
        self.expires_at = 0.0
        self.queries: list[dict] = []

    def begin(self, identity: Identity, ttl: float) -> None:
        self.identity, self.queries = identity, []
        self.expires_at = time.monotonic() + min(ttl, MAX_CONTEXT_SECONDS)

    def end(self) -> list[dict]:
        ran, self.identity, self.queries = self.queries, None, []
        return ran

    def current(self) -> Identity:
        if self.identity is None or time.monotonic() > self.expires_at:
            self.identity = None
            raise QueryError("No question is in progress, so there is no one to read data for.")
        return self.identity


context = Context()


def answer(call) -> dict:
    try:
        return call(context.current())
    except QueryError as error:
        return {"error": str(error)}


@mcp.tool()
def describe_schema() -> dict:
    """List the tables and columns you can query, their types, how they relate, and notes on
    what the values mean. Call this before writing a query."""
    return answer(queries.describe_schema)


@mcp.tool()
def run_query(sql: str) -> dict:
    """Run one read-only PostgreSQL SELECT and get the rows back (at most 1,000; 10 second
    limit). Compute totals, averages, rankings and date arithmetic in the query itself.
    The result only contains rows the person asking is allowed to see."""
    result = answer(lambda identity: queries.run_query(identity, sql))
    if "error" in result:
        context.queries.append({"sql": sql, "error": result["error"]})
    else:
        context.queries.append({**result, "rows": result["rows"][:KEPT_ROWS]})
    return result


@mcp.tool()
def sample_rows(table: str) -> dict:
    """Return five rows of a table, to see what its values look like."""
    return answer(lambda identity: queries.sample_rows(identity, table))


def has_key(request: Request, header: str, variable: str) -> bool:
    expected = os.environ.get(variable, "")
    given = request.headers.get(header, "").removeprefix("Bearer ")
    return bool(expected) and secrets.compare_digest(given, expected)


async def begin_context(request: Request) -> JSONResponse:
    if not has_key(request, "X-Context-Key", "CRM_DATA_CONTEXT_KEY"):
        return JSONResponse({"detail": "Wrong context key"}, status_code=401)
    body = await request.json()
    if body.get("role") not in ("admin", "user"):
        return JSONResponse({"detail": "role must be admin or user"}, status_code=422)
    context.begin(Identity(int(body["user_id"]), body["role"]), float(body.get("ttl_seconds", 300)))
    return JSONResponse({"active": True})


async def end_context(request: Request) -> JSONResponse:
    if not has_key(request, "X-Context-Key", "CRM_DATA_CONTEXT_KEY"):
        return JSONResponse({"detail": "Wrong context key"}, status_code=401)
    return JSONResponse({"queries": context.end()})


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


class RequireMcpKey:
    """Rejects MCP requests that do not carry the bearer token."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and not has_key(
            Request(scope), "Authorization", "CRM_DATA_MCP_KEY"
        ):
            await JSONResponse({"detail": "Wrong MCP key"}, status_code=401)(scope, receive, send)
            return
        await self.app(scope, receive, send)


def build_app() -> Starlette:
    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        host="0.0.0.0",
        # Reached by service name on a private Docker network, not from a browser.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette):
        async with mcp.session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/health", health),
            Route("/context", begin_context, methods=["POST"]),
            Route("/context", end_context, methods=["DELETE"]),
            Mount("/mcp", app=RequireMcpKey(mcp_app)),
        ],
        lifespan=lifespan,
    )


if __name__ == "__main__":
    uvicorn.run(build_app(), host="0.0.0.0", port=8765)

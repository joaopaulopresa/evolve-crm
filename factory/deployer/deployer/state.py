"""What the deployer remembers between restarts: which commits passed checks, and the releases."""

import json
from datetime import UTC, datetime
from pathlib import Path


class State:
    def __init__(self, directory: Path):
        self.file = directory / "deployer.json"
        directory.mkdir(parents=True, exist_ok=True)
        self.data = (
            json.loads(self.file.read_text())
            if self.file.exists()
            else {"checked": {}, "releases": []}
        )

    def save(self) -> None:
        self.file.write_text(json.dumps(self.data, indent=1))

    # --- checks ---------------------------------------------------------------------------

    def record_check(self, sha: str, branch: str, passed: bool) -> None:
        self.data["checked"][sha] = {"branch": branch, "passed": passed}
        self.save()

    def passed_check(self, sha: str) -> str | None:
        """The branch whose checks passed for this commit, if any."""
        entry = self.data["checked"].get(sha)
        return entry["branch"] if entry and entry["passed"] else None

    # --- releases -------------------------------------------------------------------------

    def record_release(self, sha: str, kind: str, ok: bool, **extra) -> dict:
        entry = {"sha": sha, "kind": kind, "ok": ok, "at": datetime.now(UTC).isoformat(), **extra}
        self.data["releases"].append(entry)
        self.save()
        return entry

    @property
    def releases(self) -> list[dict]:
        return self.data["releases"]

    @property
    def current(self) -> str | None:
        """The commit production is serving: the last release that went well."""
        return next((r["sha"] for r in reversed(self.releases) if r["ok"]), None)

    @property
    def rollback_target(self) -> str | None:
        """The commit production served before the current one."""
        current = self.current
        return next(
            (r["sha"] for r in reversed(self.releases) if r["ok"] and r["sha"] != current), None
        )

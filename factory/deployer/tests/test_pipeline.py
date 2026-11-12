import subprocess
from pathlib import Path

import pytest

from deployer.config import Config
from deployer.pipeline import ZERO, Pipeline, request_id
from deployer.state import State


class Harness:
    """A real bare repository, with the scripts replaced by a recorder."""

    def __init__(self, tmp: Path):
        self.work = tmp / "checkout"
        self.bare = tmp / "repo.git"
        self.calls: list[tuple[str, list[str]]] = []
        self.events: list[tuple[str, dict]] = []
        self.failing: set[str] = set()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.bare], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", self.work], check=True)
        self.git("config", "user.email", "test@example.test")
        self.git("config", "user.name", "Test")
        self.git("remote", "add", "origin", str(self.bare))
        config = Config(
            git_dir=self.bare,
            state_dir=tmp / "state",
            work_dir=tmp / "work",
            git_url=str(self.bare),
        )
        self.state = State(config.state_dir)
        self.pipeline = Pipeline(config, self.state, self.run, self.report)

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.work, check=True, capture_output=True, text=True
        ).stdout.strip()

    def commit(self, branch: str, name: str) -> str:
        self.git("checkout", "-q", "-B", branch)
        (self.work / "deploy").mkdir(exist_ok=True)
        (self.work / "deploy" / name).write_text(name)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", name)
        self.git("push", "-q", "-f", "origin", branch)
        return self.git("rev-parse", "HEAD")

    def run(self, scripts: Path, script: str, args: list[str]) -> tuple[int, str]:
        self.calls.append((script, args))
        key = f"{script} {args[0]}" if script in ("deploy.sh", "preview.sh") else script
        failed = key in self.failing or f"{script} {args[-1]}" in self.failing
        return (1, f"{script} failed") if failed else (0, f"{script} ok\nhttp://localhost:8207")

    def report(self, kind: str, fields: dict) -> None:
        self.events.append((kind, fields))

    def kinds(self) -> list[str]:
        return [kind for kind, _ in self.events]

    def scripts_run(self) -> list[str]:
        return [
            f"{script} {args[0]}" if script == "preview.sh" else script
            for script, args in self.calls
        ]


@pytest.fixture
def h(tmp_path) -> Harness:
    return Harness(tmp_path)


def install(h: Harness) -> str:
    sha = h.commit("main", "v1")
    h.pipeline.pushed("refs/heads/main", ZERO, sha)
    h.calls.clear()
    h.events.clear()
    return sha


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("cr/12", 12),
        ("cr/12-lead-source", 12),
        ("refs/heads/cr/7", 7),
        ("feature/x", None),
        ("cr/x", None),
    ],
)
def test_request_id_is_read_from_the_branch_name(name, expected):
    assert request_id(name) == expected


def test_first_push_to_main_builds_and_deploys_production(h):
    sha = h.commit("main", "v1")

    h.pipeline.pushed("refs/heads/main", ZERO, sha)

    assert h.scripts_run() == ["build.sh", "deploy.sh"]
    assert h.kinds() == ["deploy_started", "deployed"]
    assert h.state.current == sha


def test_pushed_branch_is_checked_then_previewed(h):
    main = install(h)
    sha = h.commit("cr/7-lead-source", "change")

    h.pipeline.pushed("refs/heads/cr/7-lead-source", ZERO, sha)

    assert h.scripts_run() == ["checks.sh", "preview.sh up"]
    assert h.calls[0][1][1:] == [main, sha], "checks compare the branch with where it left main"
    assert h.kinds() == ["checks_started", "checks_passed", "preview_ready"]
    assert h.events[-1][1] == {
        "change_request_id": 7,
        "branch": "cr/7-lead-source",
        "sha": sha,
        "url": "http://localhost:8207",
    }


def test_failed_checks_stop_before_the_preview(h):
    install(h)
    sha = h.commit("cr/7", "change")
    h.failing.add("checks.sh")

    h.pipeline.pushed("refs/heads/cr/7", ZERO, sha)

    assert h.scripts_run() == ["checks.sh"]
    assert h.kinds() == ["checks_started", "checks_failed"]
    assert h.pipeline.can_merge(sha, lambda cr, s: True)[0] is False


def test_scripts_come_from_main_not_from_the_branch(h):
    main = install(h)
    sha = h.commit("cr/7", "change")

    assert h.pipeline.scripts() == h.pipeline.config.work_dir / main / "deploy"
    assert not (h.pipeline.scripts() / "change").exists()
    assert (h.pipeline.export(sha) / "deploy" / "change").exists()


def test_main_may_only_move_to_a_checked_and_approved_commit(h):
    install(h)
    sha = h.commit("cr/7", "change")
    unchecked = h.pipeline.can_merge(sha, lambda cr, s: True)
    h.pipeline.pushed("refs/heads/cr/7", ZERO, sha)

    assert unchecked[0] is False
    assert h.pipeline.can_merge(sha, lambda cr, s: False)[0] is False
    assert h.pipeline.can_merge(sha, lambda cr, s: (cr, s) == (7, sha))[0] is True


def test_merging_an_approved_request_deploys_without_rebuilding_and_removes_the_preview(h):
    main = install(h)
    sha = h.commit("cr/7", "change")
    h.pipeline.pushed("refs/heads/cr/7", ZERO, sha)
    h.calls.clear()
    h.events.clear()

    h.pipeline.pushed("refs/heads/main", main, sha)

    assert h.scripts_run() == ["deploy.sh", "preview.sh down"]
    assert h.kinds() == ["deploy_started", "deployed"]
    assert h.events[-1][1]["change_request_id"] == 7
    assert (h.state.current, h.state.rollback_target) == (sha, main)


def test_failed_deploy_restores_the_previous_release(h):
    main = install(h)
    sha = h.commit("cr/7", "change")
    h.pipeline.pushed("refs/heads/cr/7", ZERO, sha)
    h.calls.clear()
    h.events.clear()
    h.failing.add(f"deploy.sh {sha}")

    h.pipeline.pushed("refs/heads/main", main, sha)

    assert [args[-1] for script, args in h.calls if script == "deploy.sh"] == [sha, main]
    assert h.kinds() == ["deploy_started", "deploy_failed"]
    assert h.events[-1][1]["restored"] == main
    assert h.state.current == main
    assert "preview.sh down" not in h.scripts_run(), "the preview stays for another attempt"


def test_rollback_redeploys_the_previous_release_and_can_be_undone(h):
    main = install(h)
    sha = h.commit("cr/7", "change")
    h.pipeline.pushed("refs/heads/cr/7", ZERO, sha)
    h.pipeline.pushed("refs/heads/main", main, sha)
    h.events.clear()

    h.pipeline.rollback(requested_by="admin@evolve.test")

    assert h.kinds() == ["deploy_started", "rolled_back"]
    assert h.events[-1][1] | {"log": ""} == {
        "change_request_id": 7,
        "sha": main,
        "from": sha,
        "requested_by": "admin@evolve.test",
        "log": "",
    }
    assert (h.state.current, h.state.rollback_target) == (main, sha)


def test_rollback_without_an_earlier_release_reports_why(h):
    install(h)

    h.pipeline.rollback()

    assert h.kinds() == ["rollback_failed"]


def test_deleting_a_request_branch_removes_its_preview(h):
    install(h)

    h.pipeline.pushed("refs/heads/cr/7", "a" * 40, ZERO)

    assert h.scripts_run() == ["preview.sh down"]


def test_state_survives_a_restart(h):
    sha = install(h)

    assert State(h.pipeline.config.state_dir).current == sha


def test_merge_moves_main_to_the_approved_commit(h):
    install(h)
    sha = h.commit("cr/7", "change")

    h.pipeline.merge(7, sha)

    assert h.pipeline.main_sha() == sha
    assert h.kinds() == []


def test_merge_that_the_repository_rejects_is_reported(h):
    install(h)
    sha = h.commit("cr/7", "change")
    hook = h.bare / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho 'Rejected: not approved'\nexit 1\n")
    hook.chmod(0o755)

    h.pipeline.merge(7, sha)

    assert h.pipeline.main_sha() != sha
    assert h.kinds() == ["merge_failed"]
    assert "Rejected: not approved" in h.events[-1][1]["log"]


def test_on_start_a_main_that_moved_unnoticed_is_deployed_once(h):
    sha = h.commit("main", "v1")

    h.pipeline.reconcile()
    h.pipeline.reconcile()

    assert h.scripts_run() == ["build.sh", "deploy.sh"]
    assert h.state.current == sha


def test_on_start_nothing_happens_without_commits(h):
    h.pipeline.reconcile()

    assert h.calls == []

"""The local delivery pipeline. Every step is a script in deploy/; this module only decides
which script runs when, remembers the outcome and tells the CRM what happened."""

import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from deployer.config import Config
from deployer.state import State

ZERO = "0" * 40
MAIN = "refs/heads/main"
BRANCH_PREFIX = "refs/heads/cr/"

# (script name, arguments) -> (exit code, output)
Runner = Callable[[Path, str, list[str]], tuple[int, str]]
# (event kind, fields) -> None
Reporter = Callable[[str, dict], None]


def request_id(ref_or_branch: str) -> int | None:
    """cr/12, cr/12-lead-source and refs/heads/cr/12 all belong to change request 12."""
    match = re.search(r"(?:^|/)cr/(\d+)(?:-[\w.-]*)?$", ref_or_branch)
    return int(match.group(1)) if match else None


class Pipeline:
    def __init__(self, config: Config, state: State, run: Runner, report: Reporter):
        self.config, self.state, self.run, self.report = config, state, run, report

    # --- git ------------------------------------------------------------------------------

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", f"--git-dir={self.config.git_dir}", *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def main_sha(self) -> str | None:
        try:
            return self.git("rev-parse", "--verify", "-q", MAIN)
        except subprocess.CalledProcessError:
            return None

    def export(self, sha: str) -> Path:
        """The files of one commit, in a directory of their own."""
        target = self.config.work_dir / sha
        if not target.exists():
            partial = target.with_suffix(".partial")
            shutil.rmtree(partial, ignore_errors=True)
            partial.mkdir(parents=True)
            archive = subprocess.Popen(
                ["git", f"--git-dir={self.config.git_dir}", "archive", sha], stdout=subprocess.PIPE
            )
            subprocess.run(["tar", "-x", "-C", str(partial)], stdin=archive.stdout, check=True)
            if archive.wait() != 0:
                raise RuntimeError(f"git archive failed for {sha}")
            partial.rename(target)
        return target

    def scripts(self) -> Path:
        """Scripts always come from main, never from the branch under test."""
        return self.export(self.main_sha()) / "deploy"

    # --- events from git ------------------------------------------------------------------

    def pushed(self, ref: str, old: str, new: str) -> None:
        if ref == MAIN:
            self.main_updated(old, new)
        elif ref.startswith(BRANCH_PREFIX):
            self.branch_pushed(ref.removeprefix("refs/heads/"), new)

    def branch_pushed(self, branch: str, sha: str) -> None:
        cr = request_id(branch)
        if cr is None:
            return
        if sha == ZERO:
            self.discard(cr)
            return
        fields = {"change_request_id": cr, "branch": branch, "sha": sha}
        self.report("checks_started", fields)
        base = self.git("merge-base", MAIN, sha)
        code, output = self.run(self.scripts(), "checks.sh", [str(self.export(sha)), base, sha])
        self.state.record_check(sha, branch, passed=code == 0)
        if code != 0:
            self.report("checks_failed", {**fields, "log": output})
            return
        self.report("checks_passed", {**fields, "log": output})

        code, output = self.run(
            self.scripts(), "preview.sh", ["up", str(cr), str(self.export(sha)), sha]
        )
        if code != 0:
            self.report("preview_failed", {**fields, "log": output})
            return
        self.report("preview_ready", {**fields, "url": output.strip().splitlines()[-1]})

    def can_merge(self, sha: str, approved: Callable[[int, str], bool]) -> tuple[bool, str]:
        """May main move to this commit? Only an approved change request whose checks passed."""
        branch = self.state.passed_check(sha)
        if branch is None:
            return False, "This commit has not passed the checks as a cr/* branch."
        cr = request_id(branch)
        if not approved(cr, sha):
            return False, f"Change request {cr} is not approved for this commit."
        return True, f"Change request {cr} is approved."

    def merge(self, cr: int, sha: str) -> None:
        """Move main to an approved commit by pushing through the git server, so the same hook
        that guards everyone else's pushes decides. The deployer has no way around it."""
        try:
            subprocess.run(
                [
                    "git",
                    f"--git-dir={self.config.git_dir}",
                    "push",
                    self.config.git_url,
                    f"{sha}:{MAIN}",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            self.report(
                "merge_failed",
                {"change_request_id": cr, "sha": sha, "log": error.stderr or error.stdout},
            )

    def main_updated(self, old: str, sha: str) -> None:
        branch = self.state.passed_check(sha)
        cr = request_id(branch) if branch else None
        fields = {"change_request_id": cr, "sha": sha}
        src = self.export(sha)
        if branch is None:
            # Installation or an operator push: nothing built these images yet.
            code, output = self.run(src / "deploy", "build.sh", [str(src), sha])
            if code != 0:
                self.state.record_release(sha, "deploy", ok=False, change_request_id=cr)
                self.report("deploy_failed", {**fields, "log": output})
                return
        self.deploy(sha, "deploy", fields)
        if cr is not None and self.state.current == sha:
            self.run(self.scripts(), "preview.sh", ["down", str(cr)])

    # --- production -----------------------------------------------------------------------

    def deploy(self, sha: str, kind: str, fields: dict) -> bool:
        previous = self.state.current
        self.report("deploy_started", fields)
        src = self.export(sha)
        code, output = self.run(self.scripts(), "deploy.sh", ["production", str(src), sha])
        self.state.record_release(
            sha, kind, ok=code == 0, change_request_id=fields.get("change_request_id")
        )
        if code == 0:
            self.report(
                "rolled_back" if kind == "rollback" else "deployed", {**fields, "log": output}
            )
            return True

        if previous and previous != sha:
            back, back_output = self.run(
                self.scripts(), "deploy.sh", ["production", str(self.export(previous)), previous]
            )
            self.state.record_release(previous, "auto_rollback", ok=back == 0)
            output += f"\n--- automatic rollback to {previous[:10]} ---\n{back_output}"
        self.report("deploy_failed", {**fields, "log": output, "restored": previous})
        return False

    def rollback(self, requested_by: str | None = None) -> None:
        target = self.state.rollback_target
        if target is None:
            self.report("rollback_failed", {"log": "There is no earlier release to roll back to."})
            return
        left = self.state.current
        cr = next(
            (r.get("change_request_id") for r in reversed(self.state.releases) if r["sha"] == left),
            None,
        )
        self.deploy(
            target,
            "rollback",
            {"change_request_id": cr, "sha": target, "from": left, "requested_by": requested_by},
        )

    def discard(self, cr: int) -> None:
        self.run(self.scripts(), "preview.sh", ["down", str(cr)])
        self.report("preview_removed", {"change_request_id": cr})

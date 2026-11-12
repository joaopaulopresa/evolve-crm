"""Tests for the pure-git checks. Run: pytest deploy/tests (needs git and python, no Docker)."""

import os
import subprocess
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[1]
MIGRATION = """
from alembic import op
import sqlalchemy as sa

def upgrade():
    {upgrade}

def downgrade():
    op.drop_column("contacts", "lead_source")
"""


class Repo:
    def __init__(self, path: Path):
        self.path = path
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.test")
        self.git("config", "user.name", "Test")
        self.commit(
            {"api/app/models.py": "x = 1\n", "api/migrations/versions/001_initial.py": "a = 1\n"}
        )
        self.base = self.git("rev-parse", "HEAD")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.path, check=True, capture_output=True, text=True
        ).stdout.strip()

    def commit(self, files: dict[str, str | None]) -> str:
        for name, content in files.items():
            target = self.path / name
            if content is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change")
        return self.git("rev-parse", "HEAD")

    def run(self, script: str, head: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(DEPLOY / script), self.base, head],
            env={**os.environ, "GIT_DIR": str(self.path / ".git")},
            capture_output=True,
            text=True,
        )


@pytest.fixture
def repo(tmp_path) -> Repo:
    return Repo(tmp_path)


def test_ordinary_code_changes_pass_the_path_check(repo):
    head = repo.commit(
        {"api/app/models.py": "x = 2\n", "web/src/pages/Contacts.tsx": "export {}\n"}
    )

    result = repo.run("check_paths.sh", head)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "path",
    [
        "deploy/deploy.sh",
        "factory/deployer/app.py",
        ".github/workflows/ci.yml",
        "docker-compose.yml",
        "docker-compose.factory.yml",
        "api/Dockerfile",
        "web/Dockerfile",
        ".env",
        ".env.example",
        "AGENTS.md",
        "api/app/auth.py",
        "api/app/implementation/router.py",
        "api/migrations/env.py",
    ],
)
def test_protected_paths_are_rejected(repo, path):
    head = repo.commit({path: "changed\n"})

    result = repo.run("check_paths.sh", head)

    assert result.returncode == 1
    assert path in result.stdout


def test_additive_migration_passes(repo):
    upgrade = 'op.add_column("contacts", sa.Column("lead_source", sa.String(40), nullable=True))'
    head = repo.commit(
        {"api/migrations/versions/002_lead_source.py": MIGRATION.format(upgrade=upgrade)}
    )

    result = repo.run("check_migrations.py", head)

    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("upgrade", "reason"),
    [
        ('op.drop_column("contacts", "phone")', "drops a column"),
        ('op.drop_table("activities")', "drops a table"),
        ('op.rename_table("deals", "opportunities")', "renames a table"),
        ('op.alter_column("contacts", "phone", new_column_name="mobile")', "renames a column"),
        ('op.alter_column("deals", "value", type_=sa.Integer())', "changes a column type"),
        ('op.alter_column("contacts", "email", nullable=False)', "makes a column NOT NULL"),
        ('op.execute("DELETE FROM contacts")', "raw SQL"),
        (
            'op.add_column("contacts", sa.Column("lead_source", sa.String(40), nullable=False))',
            "NOT NULL column without a server default",
        ),
    ],
)
def test_migrations_that_break_rollback_are_rejected(repo, upgrade, reason):
    head = repo.commit({"api/migrations/versions/002_change.py": MIGRATION.format(upgrade=upgrade)})

    result = repo.run("check_migrations.py", head)

    assert result.returncode == 1
    assert reason in result.stdout


def test_not_null_column_with_a_server_default_passes(repo):
    upgrade = (
        'op.add_column("contacts", sa.Column("lead_source", sa.String(40), '
        'nullable=False, server_default="unknown"))'
    )
    head = repo.commit(
        {"api/migrations/versions/002_lead_source.py": MIGRATION.format(upgrade=upgrade)}
    )

    assert repo.run("check_migrations.py", head).returncode == 0


def test_editing_or_deleting_an_existing_migration_is_rejected(repo):
    edited = repo.commit({"api/migrations/versions/001_initial.py": "a = 2\n"})
    assert repo.run("check_migrations.py", edited).returncode == 1

    deleted = repo.commit({"api/migrations/versions/001_initial.py": None})
    result = repo.run("check_migrations.py", deleted)
    assert result.returncode == 1
    assert "must not be edited or deleted" in result.stdout

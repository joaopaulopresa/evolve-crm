#!/usr/bin/env python3
"""Fail when the commits between BASE and HEAD contain a migration that is unsafe to roll back.

Production rolls back by running the previous release's code against the current schema, so a
migration must leave the previous release working:

- existing migration files are never edited or deleted, only new ones are added;
- upgrade() does not drop or rename tables or columns, and does not run raw SQL;
- a new NOT NULL column has a server default (the old code does not know it has to fill it).

Usage: GIT_DIR=/path/to/repo.git deploy/check_migrations.py <base-sha> <head-sha>
"""

import ast
import subprocess
import sys

MIGRATIONS = "api/migrations/versions/"
FORBIDDEN = {
    "drop_table": "drops a table",
    "drop_column": "drops a column",
    "rename_table": "renames a table",
    "execute": "runs raw SQL, which cannot be checked",
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((item.value for item in call.keywords if item.arg == name), None)


def is_false(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def problems_in(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [f"is not valid Python ({error.msg}, line {error.lineno})"]
    upgrade = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade"),
        None,
    )
    if upgrade is None:
        return ["has no upgrade() function"]

    found = []
    for call in (node for node in ast.walk(upgrade) if isinstance(node, ast.Call)):
        name = call.func.attr if isinstance(call.func, ast.Attribute) else None
        if name in FORBIDDEN:
            found.append(f"line {call.lineno}: {FORBIDDEN[name]}")
        elif name == "alter_column":
            if keyword(call, "new_column_name") is not None:
                found.append(f"line {call.lineno}: renames a column")
            if keyword(call, "type_") is not None:
                found.append(f"line {call.lineno}: changes a column type")
            if is_false(keyword(call, "nullable")):
                found.append(f"line {call.lineno}: makes a column NOT NULL")
        elif name == "add_column":
            for column in (arg for arg in call.args if isinstance(arg, ast.Call)):
                if is_false(keyword(column, "nullable")) and keyword(column, "server_default") is None:
                    found.append(f"line {call.lineno}: adds a NOT NULL column without a server default")
    return found


def main(base: str, head: str) -> int:
    failures = []
    for line in git("diff", "--name-status", "--no-renames", base, head, "--", MIGRATIONS).splitlines():
        status, path = line.split("\t", 1)
        if not path.endswith(".py"):
            continue
        if status != "A":
            failures.append(f"{path}: existing migrations must not be edited or deleted")
            continue
        failures += [f"{path}: {problem}" for problem in problems_in(git("show", f"{head}:{path}"))]

    if failures:
        print("Migrations are not safe to roll back:")
        print("\n".join(f"  {failure}" for failure in failures))
        return 1
    print("Migrations: safe to roll back.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))

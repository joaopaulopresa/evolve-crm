"""The agent's brief must fit in what Hermes injects into the prompt.

Hermes loads AGENTS.md as a context file and truncates it (keeping the head and the tail) when
it is larger than its limit: 6% of the model's context window, never less than 20,000
characters. Staying under that floor means the file is never cut, whatever the model.
The live half of this check, that the last line really reaches the model, is
`evolve-check-brief` inside the builder container.
"""

from pathlib import Path

import pytest

BRIEF = Path(__file__).resolve().parents[2] / "AGENTS.md"
CONTEXT_FILE_FLOOR = 20_000
MARKER = "EVOLVE-BRIEF-END-7Q2"

pytestmark = pytest.mark.skipif(not BRIEF.exists(), reason="AGENTS.md is not in this checkout")


def test_brief_is_smaller_than_the_context_file_limit():
    assert len(BRIEF.read_text()) < CONTEXT_FILE_FLOOR


def test_brief_ends_with_the_marker_the_live_check_asks_for():
    assert BRIEF.read_text().rstrip().splitlines()[-1].endswith(MARKER)


def test_brief_lists_every_protected_path():
    brief = BRIEF.read_text()
    patterns = (BRIEF.parent / "deploy" / "protected-paths.txt").read_text().splitlines()
    for pattern in (line for line in patterns if line and not line.startswith("#")):
        name = pattern.replace("/**", "/").replace("**/", "")
        assert name in brief, f"{pattern} is protected but the brief does not say so"

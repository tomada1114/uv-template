"""The Claude Code and Codex CLI sub-agent tiers describe the same three agents."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
# tier -> (Claude Code model alias, effort, Codex model or None to inherit the session's)
TIERS = {
    "executor": ("opus", "low", None),
    "architect": ("opus", "high", None),
    "worker": ("haiku", "max", "gpt-6-luna"),
}


def _claude_definition(tier: str) -> tuple[dict[str, str], str]:
    text = (REPO_ROOT / ".claude" / "agents" / f"{tier}.md").read_text("utf-8")
    match = re.match(r"^---\n(?P<front>.*?)\n---\n(?P<body>.*)$", text, re.DOTALL)
    assert match is not None, f"{tier}.md has no frontmatter"
    front = dict(
        line.split(": ", 1)
        for line in match["front"].splitlines()
        if re.match(r"^(name|model|effort): ", line)
    )
    return front, match["body"].strip()


def test_tier_directories_hold_exactly_the_three_tiers() -> None:
    claude = {p.stem for p in (REPO_ROOT / ".claude" / "agents").glob("*.md")}
    codex = {p.stem for p in (REPO_ROOT / ".codex" / "agents").glob("*.toml")}

    assert claude == set(TIERS)
    assert codex == set(TIERS)


@pytest.mark.parametrize("tier", sorted(TIERS))
def test_tier_definitions_agree_across_hosts(tier: str) -> None:
    model, effort, codex_model = TIERS[tier]
    front, body = _claude_definition(tier)
    codex = tomllib.loads(
        (REPO_ROOT / ".codex" / "agents" / f"{tier}.toml").read_text("utf-8")
    )

    assert front == {"name": tier, "model": model, "effort": effort}
    assert codex["name"] == tier
    assert codex["model_reasoning_effort"] == effort
    assert codex.get("model") == codex_model
    assert codex["developer_instructions"].strip() == body

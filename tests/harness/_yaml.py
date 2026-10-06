"""A fail-closed block scanner for the YAML layouts this repository commits.

No YAML library is a declared dependency, so the harness reads workflows, issue
forms, and dependabot.yml with this scanner. It reads block mappings, block
sequences, one-line flow lists, and plain or quoted scalars; every line deeper
than a key is that key's block, so a block scalar (``run: |``) is kept as raw
lines and never parsed. Any layout it cannot read raises
`UnreadableYamlError`, so a check never passes on a file it did not understand.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# One entry of a block mapping: its inline value (comment included) and the
# deeper lines below it.
type Entry = tuple[str, list[str]]
type Mapping = dict[str, Entry]

_KEY = re.compile(
    r"^(?P<indent> *)(?P<key>[\"']?[A-Za-z0-9_-]+[\"']?):(?:\s+(?P<value>.*?))?\s*$"
)
_QUOTES = {'"', "'"}


class UnreadableYamlError(AssertionError):
    """A file uses a YAML layout the scanner does not understand."""


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def content_lines(text: str) -> list[str]:
    """Return the lines that carry content: no blank or comment-only line."""
    return [
        line.rstrip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def children(lines: list[str], start: int, path: Path) -> list[str]:
    """Return the block of lines deeper than ``lines[start]``."""
    parent = _indent(lines[start])
    block: list[str] = []
    for line in lines[start + 1 :]:
        if _indent(line) <= parent:
            break
        block.append(line)
    if block and any(_indent(line) < _indent(block[0]) for line in block):
        msg = f"{path.name}: inconsistent indentation under {lines[start]!r}"
        raise UnreadableYamlError(msg)
    return block


def mapping(lines: list[str], path: Path) -> Mapping:
    """Split a block into ``key -> (inline value, child lines)`` at its own indent."""
    if not lines:
        return {}
    indent = _indent(lines[0])
    result: Mapping = {}
    for index, line in enumerate(lines):
        if _indent(line) != indent:
            continue
        match = _KEY.match(line)
        if match is None:
            msg = f"{path.name}: cannot read {line!r}"
            raise UnreadableYamlError(msg)
        result[match["key"].strip("\"'")] = (
            match["value"] or "",
            children(lines, index, path),
        )
    return result


def sequence(lines: list[str], path: Path) -> list[list[str]]:
    """Split a block sequence into each item's lines, re-indented as a block.

    ``- uses: x`` followed by ``  with:`` becomes ``uses: x`` and ``with:`` at
    one indent, so `mapping` reads the item.
    """
    if not lines:
        return []
    indent = _indent(lines[0])
    items: list[list[str]] = []
    for line in lines:
        if _indent(line) > indent and items:
            items[-1].append(line)
            continue
        body = line[indent:]
        if body != "-" and not body.startswith("- "):
            msg = f"{path.name}: expected a list item, got {line!r}"
            raise UnreadableYamlError(msg)
        rest = body[1:].lstrip()
        items.append([" " * (len(line) - len(rest)) + rest] if rest else [])
    return items


def split_comment(value: str) -> tuple[str, str | None]:
    """Split an inline value into its text and its trailing ``# comment``."""
    quote: str | None = None
    for index, char in enumerate(value):
        if quote is not None:
            quote = None if char == quote else quote
        elif char in _QUOTES and (index == 0 or value[index - 1].isspace()):
            quote = char
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip(), value[index:]
    return value.strip(), None


def scalar(value: str) -> str:
    """Return an inline value without its comment or its surrounding quotes."""
    text, _ = split_comment(value)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in _QUOTES:
        return text[1:-1]
    return text


def flow_list(value: str, path: Path) -> list[str] | None:
    """Return the items of a one-line ``[a, b]`` list, or None for any other value."""
    text, _ = split_comment(value)
    if not text.startswith("["):
        return None
    if not text.endswith("]"):
        msg = f"{path.name}: a flow list must close on its own line: {value!r}"
        raise UnreadableYamlError(msg)
    inner = text[1:-1].strip()
    return [scalar(item.strip()) for item in inner.split(",")] if inner else []


def scalar_list(entry: Entry, path: Path) -> list[str]:
    """Return the strings of a flow list, a block list, or a comma-separated string."""
    value, block = entry
    if block:
        if value:
            msg = f"{path.name}: a value and a block under one key: {value!r}"
            raise UnreadableYamlError(msg)
        items = sequence(block, path)
        if any(len(item) != 1 for item in items):
            msg = f"{path.name}: expected a list of one-line strings"
            raise UnreadableYamlError(msg)
        return [scalar(item[0].strip()) for item in items]
    listed = flow_list(value, path)
    if listed is not None:
        return listed
    return [part.strip() for part in scalar(value).split(",") if part.strip()]


def block_text(entry: Entry) -> str:
    """Return an entry's text: its block scalar's lines, or its inline value."""
    value, block = entry
    return "\n".join(block) if block else value

"""One safe YAML loader with explicit, fail-closed shape narrowing.

Actions event words remain strings. Scalar source metadata is retained only
for pin-version comments and shell block styles that the policy checks need.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import yaml

if TYPE_CHECKING:
    from pathlib import Path

    from yaml.nodes import MappingNode, ScalarNode

type Mapping = dict[str, object]


class UnreadableYamlError(AssertionError):
    """A YAML document or a required value has an unreadable shape."""


class _Scalar(str):
    comment: str | None
    style: str | None


# SafeLoader has no stubs; this boundary validates every consumed result.
class _Loader(yaml.SafeLoader):  # type: ignore[misc]  # PyYAML is untyped
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.source = text


_Loader.yaml_implicit_resolvers = {
    key: [
        (tag, pattern) for tag, pattern in resolvers if tag != "tag:yaml.org,2002:bool"
    ]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)


def _string(loader: _Loader, node: ScalarNode) -> _Scalar:
    value = _Scalar(loader.construct_scalar(node))
    tail = loader.source[node.end_mark.index :].split("\n", 1)[0].strip()
    value.comment = tail if tail.startswith("#") else None
    value.style = node.style
    return value


def _mapping(loader: _Loader, node: MappingNode) -> dict[object, object]:
    # Check explicit duplicates before SafeLoader expands merge keys. YAML merges
    # intentionally let an explicit field override the inherited value.
    seen: set[object] = set()
    for key_node, _ in node.value:
        key = (
            "<<"
            if key_node.tag == "tag:yaml.org,2002:merge"
            else loader.construct_object(key_node, deep=True)
        )
        try:
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None,
                    None,
                    f"duplicate key {key!r}",
                    key_node.start_mark,
                )
            seen.add(key)
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                "unhashable mapping key",
                key_node.start_mark,
            ) from exc
    loader.flatten_mapping(node)
    return {
        loader.construct_object(key, deep=True): loader.construct_object(
            value, deep=True
        )
        for key, value in node.value
    }


_Loader.add_constructor("tag:yaml.org,2002:str", _string)
_Loader.add_constructor("tag:yaml.org,2002:map", _mapping)


def load_yaml(path: Path, *, text: str | None = None) -> object:
    """Read safely; optional text is an issue template's YAML front matter."""
    try:
        loader = _Loader(path.read_text(encoding="utf-8") if text is None else text)
        try:
            result: object = loader.get_single_data()
        finally:
            loader.dispose()
    except (yaml.YAMLError, OSError, UnicodeError) as exc:
        msg = f"{path}: {exc}"
        raise UnreadableYamlError(msg) from exc
    return result


def as_mapping(value: object, where: str) -> Mapping:
    """Require a string-keyed mapping before a check consumes its fields."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        msg = f"{where}: expected mapping with string keys"
        raise UnreadableYamlError(msg)
    return cast("dict[str, object]", value)


def as_sequence(value: object, where: str) -> list[object]:
    """Require a sequence without silently treating a string as its items."""
    if not isinstance(value, list):
        msg = f"{where}: expected sequence"
        raise UnreadableYamlError(msg)
    return cast("list[object]", value)


def as_str(value: object, where: str) -> str:
    """Reject implicit conversions where the schema requires a string."""
    if not isinstance(value, str):
        msg = f"{where}: expected string"
        raise UnreadableYamlError(msg)
    return value


def scalar(value: object, where: str = "scalar") -> str:
    """Render schema scalars, including boolean policy flags and numeric versions."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    msg = f"{where}: expected scalar"
    raise UnreadableYamlError(msg)


def scalar_list(value: object, path: Path, *, where: str = "list") -> list[str]:
    """Read string-list fields; issue labels also permit comma-separated text."""
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [
        as_str(item, f"{path}: {where}[{index}]")
        for index, item in enumerate(as_sequence(value, f"{path}: {where}"))
    ]


def block_text(value: object) -> str:
    """Read a parsed run/input string rather than reconstructing YAML lines."""
    return as_str(value, "text")


def source_comment(value: object) -> str | None:
    """Return the original scalar's trailing comment, if any."""
    return value.comment if isinstance(value, _Scalar) else None


def scalar_style(value: object) -> str | None:
    """Keep literal versus folded shell blocks explicit in the needs policy."""
    return value.style if isinstance(value, _Scalar) else None

"""The values an ``LlmPort`` takes and returns, and the check every call runs first.

Kept free of any HTTP library, like the rest of the core: an adapter turns these
values into a provider's wire format and back.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, TypedDict

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

type LlmRole = Literal["system", "user", "assistant"]
LLM_ROLES: Final = frozenset({"system", "user", "assistant"})
# What a caller passes as `timeout` when it has no reason to pick another bound.
DEFAULT_LLM_TIMEOUT_SECONDS: Final = 60.0


class LlmMessage(TypedDict):
    """One chat message, in the shape OpenAI-compatible providers take."""

    role: LlmRole
    content: str


@dataclass(frozen=True, slots=True)
class LlmUsage:
    """The tokens one completion consumed, as the provider counted them."""

    prompt_tokens: int
    completion_tokens: int

    def __post_init__(self) -> None:
        """Refuse a count no provider could report.

        Raises:
            ValueError: If either count is negative, a bool, or not an int.
        """
        for name in ("prompt_tokens", "completion_tokens"):
            count = getattr(self, name)
            if not _is_int(count) or count < 0:
                msg = f"{name} must be a non-negative integer, got {count!r}"
                raise ValueError(msg)

    @property
    def total_tokens(self) -> int:
        """The prompt and completion tokens together."""
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class LlmCompletion:
    """A model's answer to one ``LlmPort.complete`` call.

    Attributes:
        text: The answer; may be empty.
        model: The model that answered, which can differ from the one asked
            for when the provider routes the request.
        finish_reason: Why generation stopped (``"stop"``, ``"length"``, ...)
            as the provider said it; passed through, not judged.
        usage: The tokens the call consumed.
    """

    text: str
    model: str
    finish_reason: str | None
    usage: LlmUsage


def check_completion_request(
    messages: Sequence[LlmMessage],
    *,
    model: str | None,
    max_tokens: int,
    timeout: float,
) -> None:
    """Reject arguments no ``LlmPort`` may send, before any request is made.

    Every adapter calls this first, so a bad argument fails the same way
    whichever adapter is wired in. The arguments come from code, not from a
    user, so a bad one is a bug: a ``ValueError`` with its traceback, never an
    ``AppError``. A service that forwards user input validates it first.

    Args:
        messages: The conversation; at least one message.
        model: A model id, or None for the adapter's configured model.
        max_tokens: The most tokens the answer may use; at least 1.
        timeout: The whole call's budget in seconds; positive and finite.

    Raises:
        ValueError: On the first argument that breaks its rule, checked in
            the order above.
    """
    if not messages:
        msg = "messages must not be empty"
        raise ValueError(msg)
    for index, message in enumerate(messages):
        # Read as untrusted: the type says LlmMessage, but nothing checks a
        # caller that builds its messages from JSON or plain dicts.
        fields: Mapping[str, object] = message
        role = fields.get("role")
        if role not in LLM_ROLES:
            allowed = ", ".join(sorted(LLM_ROLES))
            msg = f"messages[{index}] role must be one of {allowed}, got {role!r}"
            raise ValueError(msg)
        content = fields.get("content")
        if not _is_str(content):
            msg = (
                f"messages[{index}] content must be a string, "
                f"got {type(content).__name__}"
            )
            raise ValueError(msg)
    if model is not None and not model.strip():
        msg = f"model must be a non-blank model id, got {model!r}"
        raise ValueError(msg)
    if not _is_int(max_tokens) or max_tokens < 1:
        msg = f"max_tokens must be a positive integer, got {max_tokens!r}"
        raise ValueError(msg)
    if not _is_positive_finite_number(timeout):
        msg = f"timeout must be a positive finite number of seconds, got {timeout!r}"
        raise ValueError(msg)


def _is_str(value: object) -> bool:
    """Return whether ``value`` is a string.

    A bad argument is a ``ValueError`` here whatever its kind, so this stays a
    helper rather than an inline ``isinstance`` that asks for a ``TypeError``.
    """
    return isinstance(value, str)


def _is_int(value: object) -> bool:
    """Return whether ``value`` is an int and not a bool, which subclasses int."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_positive_finite_number(value: object) -> bool:
    """Return whether ``value`` is an int or float above zero, not NaN or infinite."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return math.isfinite(value) and value > 0

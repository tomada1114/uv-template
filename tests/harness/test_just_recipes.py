"""(c) Every ``just <recipe>`` the agent-facing documents name exists.

A renamed or removed recipe must not leave AGENTS.md, CLAUDE.md, a skill, or a
file under ``.github/`` pointing an agent at nothing. Only code is read, so
English prose ("just to be safe") never counts:

- in Markdown and in YAML text (issue forms and comments render as Markdown),
  the inline code spans and the lines of a shell-fenced block (a bare fence
  often holds a prompt template, so only its spans count);
- in a workflow, also the commands of each ``run:`` step;
- in a skill's own scripts (``.agents/skills/*/scripts/*.py``, not their
  tests), the code spans inside string literals and comments, which is how
  they name a recipe to an agent.

A token is ``just`` not preceded by a name character, then a recipe name, so
``just --list`` and the placeholder ``just <recipe>`` name nothing and
arguments (``just run todo list``) are ignored. ``just -f``/``--justfile``/
``-d``/``--working-directory`` points at another justfile, which this check
cannot read, so that form is reported rather than skipped.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.harness._yaml import split_comment

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    type MakeRoot = Callable[[dict[str, str]], Path]

REPO_ROOT = Path(__file__).resolve().parents[2]
JUSTFILE = "justfile"
DOCUMENT_GLOBS = (
    "AGENTS.md",
    "CLAUDE.md",
    ".agents/skills/**/*.md",
    ".github/**/*.md",
    ".github/**/*.yml",
    ".github/**/*.yaml",
)
SKILL_SCRIPTS = ".agents/skills/*/scripts/*.py"
WORKFLOW_PARENT = ".github/workflows"
# Column-0 justfile lines that look like a recipe header but are not one.
NOT_RECIPES = frozenset({"set", "export", "unexport", "import", "mod", "alias"})

_NAME = r"[A-Za-z_][A-Za-z0-9_-]*"
_RECIPE_HEADER = re.compile(rf"^@?(?P<name>{_NAME})(?:[ \t]+[^:]*?)?[ \t]*:(?!=)")
_ALIAS = re.compile(rf"^alias[ \t]+(?P<name>{_NAME})[ \t]*:=")
_TOKEN = re.compile(rf"(?<![\w./-])just\s+(?P<name>{_NAME})")
_OTHER_JUSTFILE = re.compile(
    r"(?<![\w./-])just\s+(?P<flag>-f|-d|--justfile|--working-directory)(?![\w-])"
)
_RUN_KEY = re.compile(r"^\s*(?:-\s+)?run:(?:\s+(?P<value>.*?))?\s*$")
_BLOCK_INDICATOR = re.compile(r"^[|>][+-]?[1-9]?$")
_SCRIPT_TOKENS = frozenset({tokenize.STRING, tokenize.COMMENT, tokenize.FSTRING_MIDDLE})
_FENCE = re.compile(r"^\s*(?:`{3,}|~{3,})\s*(?P<info>[\w-]*)")
# A fence in one of these is a command listing; any other (a bare one holding a
# prompt template, a python one) is prose whose inline spans alone count.
SHELL_FENCES = frozenset({"bash", "sh", "shell", "console", "zsh"})
_SPAN = re.compile(r"`([^`]+)`")


def justfile_recipes(text: str) -> set[str]:
    """Return the recipe and alias names a justfile defines."""
    names: set[str] = set()
    for line in text.splitlines():
        match = _ALIAS.match(line) or _RECIPE_HEADER.match(line)
        if match and match["name"] not in NOT_RECIPES:
            names.add(match["name"])
    return names


def _paragraphs(lines: list[str]) -> Iterator[tuple[int, str]]:
    """Yield ``(first line number, text)`` of each blank-line-separated run."""
    start, run = 0, []
    for number, line in enumerate([*lines, ""], start=1):
        if line.strip():
            start = start or number
            run.append(line)
        elif run:
            yield start, "\n".join(run)
            start, run = 0, []


def code_snippets(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line number, code)`` for each shell-fenced line and code span."""
    prose: list[str] = []
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        if match := _FENCE.match(line):
            fence = match["info"] if fence is None else None
            prose.append("")
        elif fence in SHELL_FENCES:
            yield number, line
            prose.append("")
        else:
            prose.append(line)
    for start, paragraph in _paragraphs(prose):
        for match in _SPAN.finditer(paragraph):
            yield start + paragraph.count("\n", 0, match.start()), match[1]


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def workflow_run_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line number, command)`` for each line of every ``run:`` step."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if (match := _RUN_KEY.match(line)) is None:
            continue
        value = split_comment(match["value"] or "")[0]
        if not _BLOCK_INDICATOR.match(value):
            yield index + 1, value
            continue
        key_column = line.index("run:")
        for number, body in enumerate(lines[index + 1 :], start=index + 2):
            if body.strip() and _indent(body) <= key_column:
                break
            if not body.lstrip().startswith("#"):
                yield number, split_comment(body)[0]


def script_snippets(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(line number, code)`` for each code span in a string or comment."""
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type in _SCRIPT_TOKENS:
            for match in _SPAN.finditer(token.string):
                yield (
                    token.start[0] + token.string.count("\n", 0, match.start()),
                    match[1],
                )


def documents(root: Path) -> list[Path]:
    """Return every document this check reads, sorted and without repeats."""
    patterns = (*DOCUMENT_GLOBS, SKILL_SCRIPTS)
    found = {path for pattern in patterns for path in root.glob(pattern)}
    return sorted(path for path in found if path.is_file())


def _snippets(path: Path, root: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        return list(script_snippets(text))
    snippets = list(code_snippets(text))
    if path.parent == root / WORKFLOW_PARENT:
        snippets.extend(workflow_run_lines(text))
    return snippets


def recipe_findings(root: Path) -> list[str]:
    """Return each ``just <recipe>`` a document names that the justfile lacks."""
    justfile = root / JUSTFILE
    if not justfile.is_file():
        return [f"{JUSTFILE} is missing"]
    recipes = justfile_recipes(justfile.read_text(encoding="utf-8"))
    findings: list[str] = []
    for path in documents(root):
        relative = path.relative_to(root).as_posix()
        snippets = _snippets(path, root)
        findings.extend(
            f"{relative}:{number}: `just {match['flag']}` names another justfile, "
            "which this check cannot read; name the recipe of the root justfile"
            for number, code in sorted(set(snippets))
            for match in _OTHER_JUSTFILE.finditer(code)
        )
        missing = sorted(
            {
                (number, match["name"])
                for number, code in snippets
                for match in _TOKEN.finditer(code)
                if match["name"] not in recipes
            }
        )
        findings.extend(
            f"{relative}:{number}: `just {name}` names no recipe in the {JUSTFILE}"
            for number, name in missing
        )
    return findings


# --- the repository ---


def test_recipes_named_on_repository_exist() -> None:
    assert recipe_findings(REPO_ROOT) == []


def test_justfile_recipes_reads_repository_justfile() -> None:
    recipes = justfile_recipes((REPO_ROOT / JUSTFILE).read_text(encoding="utf-8"))

    # Only the harness's own recipes: an app may delete the others (`just run`
    # goes with the CLI).
    assert {"verify", "check-harness"} <= recipes
    assert not recipes & NOT_RECIPES


# --- fixtures ---

JUSTFILE_TEXT = """\
set shell := ["bash", "-c"]
version := "1"
alias t := test

# Run the tests
test:
    uv run pytest

[positional-arguments]
run *ARGS:
    uv run app "$@"

@quiet arg="x": test
    echo {{arg}}
"""


@pytest.fixture
def make_root(tmp_path: Path) -> MakeRoot:
    def make(files: dict[str, str]) -> Path:
        (tmp_path / JUSTFILE).write_text(JUSTFILE_TEXT, encoding="utf-8")
        for relative, text in files.items():
            (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / relative).write_text(text, encoding="utf-8")
        return tmp_path

    return make


def test_justfile_recipes_reads_headers_and_aliases() -> None:
    assert justfile_recipes(JUSTFILE_TEXT) == {"t", "test", "run", "quiet"}


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("Run `just test` first.\n", id="inline-span"),
        pytest.param("```bash\njust run --help\n```\n", id="recipe-with-arguments"),
        pytest.param("Use `just t`, the alias.\n", id="alias"),
        pytest.param("It is just docs, nothing more.\n", id="prose"),
        pytest.param("```\nIts CI just failed.\n```\n", id="bare-fence-prose"),
        pytest.param("Replace `just <recipe>` or run `just --list`.\n", id="no-name"),
        pytest.param("Run `uvx --from rust-just==1 just test`.\n", id="tool-prefix"),
    ],
)
def test_recipe_findings_existing_or_no_recipe_passes(
    make_root: MakeRoot, text: str
) -> None:
    assert recipe_findings(make_root({"AGENTS.md": text})) == []


@pytest.mark.parametrize(
    ("relative", "text", "line"),
    [
        pytest.param("AGENTS.md", "# Guide\n\nRun `just docs`.\n", 3, id="agents-span"),
        pytest.param(
            "CLAUDE.md", "```bash\njust test\njust docs\n```\n", 3, id="fence"
        ),
        pytest.param(
            "CLAUDE.md", "```\nPrompt: run `just docs`.\n```\n", 2, id="bare-fence-span"
        ),
        pytest.param(
            ".agents/skills/foo/references/x.md",
            "A span may wrap: `just\ndocs` here.\n",
            1,
            id="skill-reference-wrapped-span",
        ),
        pytest.param(
            ".github/workflows/ci.yml",
            "jobs:\n  a:\n    steps:\n      - run: just docs\n",
            4,
            id="workflow-run",
        ),
        pytest.param(
            ".github/workflows/ci.yml",
            "jobs:\n  a:\n    steps:\n      - name: Check\n        run: |\n"
            "          # just a comment\n          just test\n\n"
            "          uvx --from rust-just==1 just docs # the docs\n",
            9,
            id="workflow-run-block",
        ),
        pytest.param(
            ".agents/skills/foo/scripts/tool.py",
            '"""Tool.\n\nRun `just test` first.\n"""\n'
            "# A prose comment: just fixed.\n"
            'print(f"next: `just test`, then `just docs`")  # `just t`\n',
            6,
            id="skill-script-strings",
        ),
        pytest.param(
            ".github/ISSUE_TEMPLATE/bug.yml",
            "body:\n  - type: markdown\n    attributes:\n      value: Run `just docs`.\n",
            4,
            id="issue-form",
        ),
    ],
)
def test_recipe_findings_missing_recipe_names_file_and_recipe(
    make_root: MakeRoot, relative: str, text: str, line: int
) -> None:
    findings = recipe_findings(make_root({relative: text}))

    assert findings == [
        f"{relative}:{line}: `just docs` names no recipe in the {JUSTFILE}"
    ]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("# It is just docs here.\njobs: {}\n", id="comment"),
        pytest.param(
            "jobs:\n  a:\n    name: Run just the fast checks\n    steps:\n"
            "      - name: Run just the docs\n        run: just test\n",
            id="step-and-job-names",
        ),
        pytest.param(
            "defaults:\n  run:\n    shell: bash\njobs: {}\n", id="defaults-run"
        ),
    ],
)
def test_recipe_findings_workflow_prose_is_not_a_command(
    make_root: MakeRoot, text: str
) -> None:
    assert recipe_findings(make_root({".github/workflows/ci.yml": text})) == []


def test_recipe_findings_skill_script_tests_are_not_read(make_root: MakeRoot) -> None:
    text = '"""Fixture: `just docs` is a fake recipe."""\n'

    assert (
        recipe_findings(make_root({".agents/skills/foo/scripts/tests/t.py": text}))
        == []
    )


@pytest.mark.parametrize(
    ("text", "flag"),
    [
        pytest.param("Run `just -f other/justfile docs`.\n", "-f", id="short"),
        pytest.param("Run `just --justfile=x test`.\n", "--justfile", id="long-equals"),
        pytest.param("```bash\njust -d sub test\n```\n", "-d", id="working-dir"),
    ],
)
def test_recipe_findings_other_justfile_is_reported(
    make_root: MakeRoot, text: str, flag: str
) -> None:
    findings = recipe_findings(make_root({"AGENTS.md": text}))

    assert len(findings) == 1
    assert findings[0].startswith("AGENTS.md:")
    assert f"`just {flag}` names another justfile" in findings[0]


def test_recipe_findings_without_justfile_fails(tmp_path: Path) -> None:
    assert recipe_findings(tmp_path) == [f"{JUSTFILE} is missing"]

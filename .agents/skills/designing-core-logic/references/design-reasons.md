# Why the layers are shaped this way

Read before replacing a layer, moving a rule across one, or adding a runtime dependency,
and when a rule in the skill looks arbitrary. Each reason is the current design, in the
present tense; a pull request that changes the design rewrites the reason here
(`AGENTS.md`'s "Before changing the architecture").

## A framework-free core under thin entry points

An application like this one ends up with an HTTP API, a command line, or both, and the
expensive mistake is letting either framework leak into the business rules: the rules
then cannot be tested, reused, or kept when the entry point changes. So the core imports
only the standard library — ports are `typing.Protocol`s, values are frozen dataclasses
— adapters implement its ports, and the two entry points get their services from one
composition root and only translate between their own protocol and the core.

- Ruff's banned-api rule and `tests/core/test_imports.py` keep the core clean
  ("The direction dependencies point" in the skill), so the boundary holds without a
  reviewer remembering it.
- The CLI reaches the API only through `cli/serve.py`, which imports FastAPI and uvicorn
  inside the command. Dropping the entry point an app does not need is therefore a list
  of deletions (`building-api-routes`' "A project without the API", `designing-clis`'
  "A project without the CLI"), never a refactor of the core.

## The runtime dependencies are what the entry points need

`[project] dependencies` holds exactly what the two entry points and the settings need:
FastAPI and uvicorn for the API, Typer for the CLI, and pydantic-settings for `Settings`.
Every user installs each of them, so nothing else joins without a reason.

- The SQLite adapter uses the standard library's `sqlite3` driver, not an ORM, so
  persistence adds no package. An ORM or a migration tool is a runtime dependency and a
  persistence change, each a design change of its own.
- `httpx`, which only the OpenRouter LLM adapter needs, sits in the optional `ai` extra
  (`integrating-llm`), so an app that never calls a model carries nothing extra.
- Anything else is added deliberately, with the review record `managing-dependencies`
  asks for and the owner's sign-off.

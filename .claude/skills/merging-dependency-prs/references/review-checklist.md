# Reviewing dependency PRs

Read this before approving any PR at Step 2 — this is the point of the gate, not a
formality. Step 4 repeats this review whenever a head changes:

- Read the complete current diff. For an approved plan, verify the content still fits
  its Actions, versions and unit completion.
- GitHub Actions bumps must remain **SHA-pinned with a version comment**
  (`uses: owner/repo@<40-hex SHA> # vX.Y.Z`). A diff that replaces a SHA pin with a
  floating tag is a regression — hold it. The zizmor job (`Workflow Security Lint`) and
  the `zizmor` pre-commit hook audit workflows, so such a PR should already be red.
- Check that the SHA belongs to the tag in the comment: `gh api
  repos/<owner>/<repo>/commits/<sha> -q .sha` resolves, and `gh release view <tag>
  --repo <owner>/<repo>` names the same commit. A comment that disagrees with its SHA
  is held.
- For a major bump, read the upstream release notes before approving:
  `gh release view <tag> --repo <owner>/<repo>` or the changelog link in the PR body.
- Treat a **minor change of a `0.x` Action as major risk**. The survey reports it as
  `major` with the `pre_one_minor` flag; call it out and read the release notes.
  Inspect each member of a grouped PR when its title carries no versions.
- A bump that changes anything under `.github/workflows/` beyond the `uses:` lines —
  a new input, a new step, a changed `permissions:` block or trigger — is changing
  _what_ runs rather than _which version_ runs, and goes to "Stop and ask".
- Every pin of the same Action moves together, and an Action with a pre-commit twin
  (`crate-ci/typos`) moves with its `rev:` in `.pre-commit-config.yaml` — SKILL.md
  Step 2.

## `uv` PRs

A `dependabot/uv/...` PR moves Python dependencies. Review it as closely as an Action:

- `pyproject.toml` and `uv.lock` move together. A `pyproject.toml` change arrives with
  the `uv.lock` that `uv lock` generated for it, in the same PR; a `pyproject.toml`
  change without its lock is held. A `uv.lock`-only change is a lock refresh inside
  the existing ranges and needs no `pyproject.toml` change.
- In `pyproject.toml`, only the `>=X.Y` lower bound of a dependency that already exists
  under `[project] dependencies` or `[dependency-groups]` may change. A new entry, a
  removed one, or anything under `[tool.*]` — `exclude-newer` included — goes to
  "Stop and ask".
- In `uv.lock`, every changed `[[package]]` names a package the base already locked; its
  `version`, `sdist`, and `wheels` change, nothing else. A package the base did not lock
  is a new package, transitive or not: "Stop and ask", with `managing-dependencies`'
  review record. A change under `[options]` is "Stop and ask" too.
- CI's `uv sync --group dev --locked` passed on the current head — every job starts with
  it, and it refuses a lock that disagrees with `pyproject.toml` or with the
  `exclude-newer` window. `uv lock --check` (the first step of `just verify`) passes on a
  checkout of that head.
- List every `version =` change of a grouped PR. A 0.x minor among them (`ruff`) is a
  major risk: read its changelog or release notes before approving.
- A `ruff` bump moves with the `astral-sh/ruff-pre-commit` hook's `rev:` in
  `.pre-commit-config.yaml` — SKILL.md Step 2.

---
name: release-workflow
description: >
  Cut a release - finalize the CHANGELOG, bump the version, tag, and watch the
  release pipeline through to PyPI. Use PROACTIVELY when: release, cut a
  release, tag a version, bump version, publish to PyPI, ship a version.
allowed-tools: Bash(git status:*), Bash(git log:*), Bash(gh run list:*)
---

# Release Workflow

All commit messages, PR titles, and release notes MUST be written in English.

## Dynamic Context

- Working tree status: !`git status --short`
- Recent commits: !`git log --oneline -10`
- Latest main CI run: !`gh run list --branch main -L 1`

## Step 1: Preflight

Refuse to start unless all of the following hold:

- The current branch is `main` and the working tree is clean.
- `just check` passes locally.
- The latest CI run on `main` is green (see dynamic context above).

If any fails, fix it first — a release tag on a red commit publishes a broken
artifact to PyPI, which cannot be replaced under the same version.

## Step 2: Pick the Version

Read the `## [Unreleased]` section of `CHANGELOG.md` and choose the next
version with SemVer:

| Unreleased contains | Bump |
|---------------------|------|
| Removed or incompatible public API changes | major |
| New features, backwards compatible | minor |
| Only fixes, docs, or internal changes | patch |

Before `1.0.0`, still prefer minor for features and patch for fixes — do not
jump to `1.0.0` without the user explicitly asking for it.

## Step 3: Prepare the Release Branch

Never commit directly on `main` (`no-commit-to-branch` blocks it, and
`--no-verify` is blocked by `.claude/hooks/guard.py`).

```bash
git checkout -b chore/release-vX.Y.Z
```

Then:

1. Set `version = "X.Y.Z"` under `[project]` in `pyproject.toml`.
2. In `CHANGELOG.md`, move the Unreleased entries under a new
   `## [X.Y.Z] - YYYY-MM-DD` heading and leave an empty `## [Unreleased]`
   section behind.
3. Run `uv lock` — the project's own version is recorded in `uv.lock`, so a
   version bump without it fails CI's `uv sync --locked`.
4. Run `just check`.

Commit as `chore(release): vX.Y.Z` (include `uv.lock` in the same commit).

## Step 4: Merge the Release PR

Open a PR titled `chore(release): vX.Y.Z`, wait for CI, and merge it:

```bash
gh pr create --base main --title "chore(release): vX.Y.Z" --body "..."
gh pr checks --watch --fail-fast
gh pr merge --squash --delete-branch
```

Never use `gh pr merge --admin` — it bypasses the checks that protect the tag.

## Step 5: Tag

The tag must point at the merged release commit on `main`:

```bash
git checkout main && git pull
git tag vX.Y.Z
git push origin vX.Y.Z
```

## Step 6: Watch the Pipeline

Pushing the tag triggers `.github/workflows/release.yml`, which runs the
lint and test gate, builds the distribution, publishes it to PyPI via
Trusted Publishing, and creates the GitHub Release.

```bash
gh run watch
```

Then confirm both outputs:

- The GitHub Release exists with the expected notes (`gh release view vX.Y.Z`).
- The version is on PyPI.

**Prerequisite:** PyPI Trusted Publishing must already be registered for this
repository (owner, repo, workflow `release.yml`, environment `release`) as
described in `TEMPLATE.md`. Without it the publish job fails.

## Notes

- If the publish step fails for a transient reason, re-run the workflow from
  the Actions UI or with `workflow_dispatch` — do not delete and re-push the
  tag.
- If a released version is broken, release a new patch version. PyPI does not
  allow re-uploading a version that already exists.

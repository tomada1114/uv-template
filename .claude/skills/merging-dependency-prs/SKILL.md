---
name: merging-dependency-prs
description: >
  Use when landing open Dependabot pull requests, clearing a backlog of dependency
  updates, or several bot PRs contest the same workflow file. Covers the read-only
  survey, pre-1.0 minor updates treated as major risk, review of SHA-pinned Action
  bumps, keeping an Action and its pre-commit twin on one version, an exact approval
  plan, individual merges or a combined branch, and closing originals only after their
  replacement lands. Python dependencies are updated by hand, not here.
---

# Merging Dependency PRs

**Owns:** landing already-open Dependabot PRs: survey, review, approval scope, landing
mode, the combined branch, and cleanup. **Does not own:** updating Python dependencies
— `.github/dependabot.yml` covers GitHub Actions only, and `pyproject.toml` / `uv.lock`
move by the manual procedure in `AGENTS.md` › "`[tool.uv] exclude-newer`" — nor whether
a package may be added at all (`AGENTS.md` › "Conventions: pyproject.toml").

## Operating contract

- **Input:** all open Dependabot PRs, or an explicitly selected subset.
- **Output:** verified merged PRs or a combined PR, plus held and superseded originals.
- **Approval:** do the survey and review first, present the exact plan below, then wait
  for one approval covering that plan. Carry out its approved actions without asking
  again per merge. Green CI and a branch choice provide no write authorization.
- **Boundary:** keep each check tied to the current head; honor repository-required
  checks, review, human approval, and the approved stopping point independently.

## Step 1: Survey

```bash
python3 .agents/skills/merging-dependency-prs/scripts/survey_prs.py
```

This script is read-only; `--json` exposes the same rows for a plan. If no selected bot
PR remains, report that and stop. Record ecosystem, versions, risk level, CI state,
merge state and contested paths. The survey marks a parsed 0.x minor change as `major`
and sets `pre_one_minor`, so the plan names that risk explicitly.

`.github/dependabot.yml` groups every Action into one `actions` PR a month, so a grouped
title is the usual case and hides its members: inspect the whole diff and each `uses:`
change rather than deriving the group's risk from its title. A missing or unknown
version is a reason to inspect, never a patch classification.

A row whose ecosystem is `other` is not something this repository's Dependabot config
asks for — typically a security update the repository settings enabled for `uv.lock` or
`pyproject.toml`. Hold it: a Python dependency moves only by the manual
`exclude-newer` procedure, and a `pyproject.toml`-only change cannot pass CI's
`uv sync --locked` anyway ([F4](references/failure-modes.md)). Report the advisory so a
human can schedule that update.

## Step 2: Review and coordinate

Run the [review checklist](references/review-checklist.md) for every selected PR before
making the plan. Diagnose failing checks with
[failure modes](references/failure-modes.md). Read upstream release notes for every
major, including a 0.x minor promoted to major.

Treat these as one reviewed unit:

- **Every pin of the same Action.** `actions/checkout` and `astral-sh/setup-uv` are
  pinned in many jobs across `.github/workflows/`; all of them move to the same SHA, or
  the PR is incomplete.
- **An Action and its pre-commit twin.** `crate-ci/typos` runs both as an Action in
  `ci.yml` and as a hook whose `rev:` is in `.pre-commit-config.yaml`. Dependabot only
  updates the Action, so a bump leaves local and CI spell checks on different versions
  until the hook's `rev:` follows. The same applies to any future Action that has a
  pre-commit counterpart.

If open PRs leave a unit split, complete it on the combined branch and list the exact
companion pins and target versions in the plan. Completing a unit never adds a new
Action, hook, or package — that is a separate decision.

## Step 3: Choose a mode and get approval

Merge individually only when at most three eligible PRs have no contested paths and each
is clean with passing current-head checks. Otherwise build a combined PR: more PRs,
overlapping workflow files, or a unit needing completion favor that route. Mixed
outcomes are allowed; name the mode for each PR.

The survey's passing rollup is a classifier, not the complete gate: confirm that every
expected required check actually registered and passed for the head being landed.
Pending, missing or unrecognized results hold the PR.

### The approval gate

Present one concrete plan that names:

- Every selected PR, its reviewed head and diff, landing mode, exact Actions and target
  versions/SHAs, every major/0.x minor, the release-note review, and any unit
  completion.
- Branch creation, commits and pushes, PR creation/update, which PRs will merge, and
  which originals and branches will close or be deleted after a combined merge.
- Every planned `@dependabot rebase` comment, with its target PR, and every CI rerun,
  with its run/job ID and reason.
- The rebases that an earlier approved merge may force on the remaining approved PRs.
  The one approval covers those necessary rebases too; Step 4 revalidates each new head.
- Which cases are held for a separate decision, and whether the run stops at an open
  verified combined PR or at a merge.

Wait for approval and record that scope. A new PR, Action, major, rerun, comment or
landing mode outside it needs fresh approval. "Stop and ask" applies outside any batch
approval; do not stretch a green check or an approved Action into another decision.

## Step 4: Execute the approved plan

Follow [landing](references/landing.md) for the selected mode. The combined branch
starts from the current default branch and applies the approved pins by hand-editing
only the `uses:` lines (and a twin's `rev:`); it never integrates a bot branch's
commits.

For an Action, copy the approved full SHA and its `# vX.Y.Z` comment exactly.

Record the head covered by every review. Any changed head, including a bot rebase,
invalidates the old-head evidence: repeat Step 2's complete diff, release-note and pin
review before proceeding. Compare the new content with the approved plan; hold a change
outside that scope for fresh approval. This applies to individual PRs and combined
branches, even when the rebase itself was already approved.

Run the repository's local gate (`just verify`, plus the workflow lint described in
[landing](references/landing.md#verify-and-publish)), then recheck the exact published
head's CI, feedback, and required approvals before merging. Resolve only settled
mechanical failures in scope; a migration or other judgment call is held for the human.

Close superseded originals with a pointer only after the combined PR is confirmed
merged. If it is left open or abandoned, the originals stay open too.

## Stop and ask

These require a separate decision even if a batch was approved:

- An Action update that widens `permissions:`, adds a secret, changes a trigger, or
  adds a step that was not there before.
- A maintainer, owner or source change, including an Action moving to another
  repository.
- Any Python dependency change: a Dependabot PR touching `pyproject.toml` or `uv.lock`,
  a move of `[tool.uv] exclude-newer`, or a new package in `uv.lock`.
- A bump that is green only after relaxing a gate, a zizmor finding, or an Action pin.
- An Action major whose migration changes inputs or behavior beyond a mechanical rename;
  a newly discovered breaking change outside the approved plan.
- A conflict or failure whose resolution changes application behavior or needs a new
  dependency/architecture choice.

`AGENTS.md`'s rules apply: never `--admin`, `--no-verify`, force-push, unpin an Action
or weaken a gate to land a bump. Retain the PR and branch when stopped.

## Step 5: Report

Report each merged PR and what landed, each held PR and its reason, each confirmed
superseded closure, and any real CI error with its job/head evidence. Include the
approved plan, pin review, local checks, final heads and remaining work. Partial
execution is reported as partial, never as a completed batch.

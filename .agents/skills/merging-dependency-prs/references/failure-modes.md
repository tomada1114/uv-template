# CI Failure Modes on Dependabot PRs

Read this when the survey reports `checks=FAILING`. Diagnose before deciding — most
failures here are mechanical, not regressions.

Pull the real error first:

```bash
gh run list --branch <branch> --limit 1 --json databaseId -q '.[0].databaseId' \
  | xargs -I{} gh run view {} --log-failed
```

Which _job_ failed is the fastest way to tell these apart. CI runs `Lint & Type Check`,
the sharded `Test` jobs and `Coverage`, `Spell Check`, and `Workflow Security Lint`
(zizmor).

## F1 — Workflow security lint

**Symptom:** `Workflow Security Lint` fails; everything else passes.

**Cause:** zizmor audits every workflow. A bump that drops the SHA pin, an Action
release that zizmor now flags (a known-vulnerable version, an `artipacked` or
template-injection pattern the new version introduces), or a change to
`permissions:` all land here.

**Fix:** a lost pin is a regression — hold the PR (review checklist). For a new finding,
read it: a mechanical fix inside the bumped step belongs on the branch; anything that
needs a new `# zizmor: ignore[...]`, a widened permission, or a policy change is "Stop
and ask". Never silence the audit to land a bump.

## F2 — An Action's major changed its inputs or behavior

**Symptom:** a job fails at the bumped step itself — an unknown or removed input, a
changed default, an artifact the next job can no longer find.

**Cause:** an Action major (or a 0.x minor) renamed an input, changed a default, or
changed what it produces. `astral-sh/setup-uv`, `actions/upload-artifact` and
`actions/download-artifact` are the ones whose behavior CI depends on most.

**Fix:** read the release notes. A renamed input named in the migration note is
mechanical and belongs on the branch. A change that alters how the job works — caching,
artifact layout, the Python it provisions — is a migration: hold the PR and report what
the release notes ask for.

## F3 — Cooldown

**Symptom:** a version you expected is not proposed, or a security update arrives
younger than the configured window.

**Cause:** `.github/dependabot.yml`'s `cooldown: default-days: 7`. Dependabot exempts
**security updates** from its own cooldown.

**Fix:** a security update you want now is a human decision: report the advisory, the
affected version, and its publish date, and let the owner choose between waiting out
the window and merging early.

## F4 — A Python dependency PR (`ecosystem=other`)

**Symptom:** every job fails at `uv sync --group dev --locked` (or `--group docs`),
exit code 1. The PR touches `pyproject.toml` or `uv.lock`.

**Cause:** this repository's Dependabot config does not manage Python dependencies; a
PR like this is a security update the repository settings enabled. CI installs with
`--locked`, which refuses a lockfile that disagrees with the manifest, and the
`exclude-newer` cutoff may not admit the proposed version at all.

**This is not a regression, and not this skill's to land.** Hold the PR and report the
advisory. The update goes through `managing-dependencies`' `exclude-newer` procedure as
its own reviewed change; close the bot PR only after that change lands, with a pointer
to it.

## F5 — Test or coverage failure

**Symptom:** lint passes; a `Test` shard fails, or `Coverage` drops below
`--fail-under=80`.

**Fix:** this is a real signal. Read the failure. Hold the PR and report it — do not
chase coverage by editing tests to accommodate a dependency you have not decided to
accept, and do not lower the threshold.

## F6 — Merge state `BEHIND` or `DIRTY`

Not a CI failure. `BEHIND` means main moved; `DIRTY` means a real conflict.

```bash
gh pr comment <number> --body "@dependabot rebase"
```

After the bot updates the head, repeat Step 4's review and approval-scope comparison
before accepting the new checks. An accepted comment is not proof of a completed rebase.
If repeated conflicts remain, take the PR through the approved combined-branch route; do
not widen the approved scope silently.

## F7 — Check never reports

**Symptom:** `checks=PENDING` that never resolves, or `checks=NONE`.

**Cause:** workflow concurrency cancellation, or a workflow whose triggers do not fire
for the bot's PRs.

**Fix:** re-run with `gh run rerun <run-id>` when the plan covers it. Never merge a PR
whose checks never actually ran — a missing check is not a passing check.

## F8 — Unrecognised or absent conclusion

**Symptom:** `checks=FAILING` naming a check as `<name>=STARTUP_FAILURE`,
`<name>=STALE`, or `<name>=UNKNOWN`.

**Cause:** the check did not finish in a state the classifier vouches for.
`STARTUP_FAILURE` means the runner never got the job started; `STALE` means GitHub
superseded the result; `UNKNOWN` means the rollup entry carried neither a conclusion nor
a status, which is the shape an API change or a partially-written check produces.

**Fix:** none of these is a test failure, so do not read the diff for a cause — open the
run and find out why it did not complete, then `gh run rerun <run-id>`. The verdict is
the classifier declining to vouch for the check, not a report that the check failed;
`PASSING` is an allow-list of `SUCCESS`, `NEUTRAL` and `SKIPPED`, and everything else is
held deliberately. A state that ought to pass and does not is a bug in
`scripts/survey_prs.py`'s `check_summary`, not a reason to merge past it.

---
name: cloud-claude-shipping-issues
description: >
  Claude Code cloud sessions only (CLAUDE_CODE_REMOTE=true). Use when asked to ship the
  next GitHub issue, a numbered issue, or the whole backlog, or to clear the ticket
  backlog, from a Claude Code cloud session; when the shipping-issues preflight prints
  host: cloud; or when gh pr, gh issue, or a GraphQL call answers 403 "GitHub GraphQL is
  not available from Claude Code sessions" while shipping an issue, a PR, its Codex
  review, its CI, or its merge.
---

# Shipping Issues from a Claude Code Cloud Session

**Owns:** shipping issues end to end from a Claude Code cloud session — rank, implement,
PR, review, CI, merge, follow-ups, and the session's branch between issues — over REST.
**Does not own:** the local workflow and its scripts (`shipping-issues`), Codex's
(`codex-shipping-issues`), or what an issue body and a label mean (`triaging-issues`).

Claude Code cloud sessions only. Locally, use `shipping-issues`; in Codex,
`codex-shipping-issues`. **Done:** review settled, PR merged, issue CLOSED, no gate
deleted or weakened.

## Authority

**Invoking this skill is the sign-off for exactly these remote writes, for this
invocation:** pushing its own branch (the session's designated branch), creating the
pull request, merging it once CI passes, filing and labelling follow-up issues, and
removing `blocked: dependency` from the issues its merge unblocked. Nothing else: no
force-push, no branch deletion, no reply to or resolution of a review thread, no
`@codex review`, no `just labels`, no label on any other issue, no comment, no PR edit,
no issue closed by hand, and no Auto-fix. A step that would need one stops and asks.
Commits go through `smart-commit`, under its own exception. A new dependency is
proposed, and the run waits for sign-off.

The go-ahead to merge is a settled [review](#5-wait-for-the-review) and a `PASS` for
the current head: the merge happens in that same turn, with no "shall I merge?". The
only pauses are the [stop conditions](#stop-conditions).

## Modes

| Argument | Behavior |
| --- | --- |
| _(none)_ | Ship the top-ranked shippable issue. |
| a number, e.g. `42` | Ship that issue, once nothing it depends on is open. |
| `all` | Ship every shippable issue, one at a time, re-ranking after each merge. |

## Working rules

- **Serial and inline.** One issue start to finish, on the session's one branch, in
  this session: no worktrees, no parallel sub-agents, no background commands
  ([why](references/cloud-host.md#run-state-lives-on-the-vm)).
- **REST only.** Every GitHub read and write is a `gh api repos/{owner}/{repo}/...`
  call from [rest-calls.md](references/rest-calls.md), or a built-in GitHub tool doing
  the same REST operation. Of `shipping-issues`' scripts, this skill runs only
  `issue_digest.py` (file mode), `review_watch.py`, and `run_record.py` (with
  `--repo`); the rest are local-only and are never run here.
- **A 403 for GraphQL or repository scope stops the run**: report the call and its
  message, and never retry it another way
  ([cloud-host.md](references/cloud-host.md#a-403-from-the-proxy)).
- **State lives in `<runstate>`**
  (`${AGENT_SKILL_STATE_DIR:-$HOME/.local/state/agent-skills}/shipping-issues/<owner>__<repo>`),
  never in the checkout. Record each event as it happens with
  `python3 .agents/skills/shipping-issues/scripts/run_record.py --repo <owner>/<repo>
  --event <event> --field k=v`, and re-read `<runstate>/run.md` after a compaction.
- **Waits are foreground slices** under 10 minutes, the call's timeout raised to
  match, repeated up to the step's cap — never a background command.

## Workflow

### 1. Check the host

```bash
test "$CLAUDE_CODE_REMOTE" = true && echo "host: cloud" || echo "host: local"
```

`host: local` → stop here: this is not a cloud session; use `shipping-issues`. Then
read [cloud-host.md](references/cloud-host.md) once, and the repository
([its call](references/rest-calls.md#the-repository)): `full_name`,
`default_branch`, `delete_branch_on_merge`. The branch is the one the session's
instructions name (`git branch --show-current`), never the default branch. A dirty
tree holds work this run did not make: stop and ask. Otherwise
`git fetch origin <default> && git merge --no-edit origin/<default>`; a non-empty
`git diff --stat origin/<default>` afterwards is the same stop. Record `run-start`.

### 2. Rank

Fetch the open issues and PRs and run the digest on them
([the calls](references/rest-calls.md#the-backlog-and-the-pick)). `select: none` →
report why (the `held:` line) and stop. A `tracking` issue is never shipped; its
sub-issues are. Unlabelled issues rank on their suggested `~P<n>` tier: list them in
the report, never write the label. An issue whose design is not settled
(`blocked: design` or `design=open`) is taken only by number, and only when its thread
already answers the design; otherwise stop and ask the question. Record `selection`.

### 3. Implement

Read the issue and every comment ([how](references/rest-calls.md#one-issue)), and write
an acceptance-to-check map before editing. Run the baseline once, unmodified:
`just verify > <runstate>/verify/<n>-baseline.log 2>&1`. A red baseline is checked
against the environment first — a host the network refuses, a missing tool — and
named in the report; it is not the issue's to fix. Implement inline with the skills
`AGENTS.md` routes the change to (**REQUIRED:** `tdd` for a behavior change), commit
with **REQUIRED:** `smart-commit`, and run `just verify` on the committed tree before
the push; over an environment-caused red baseline, only the baseline's own failures
may remain. Keep the change within the issue; what falls outside it goes to step 9.

### 4. Open the PR

`git push -u origin <branch>`, then create a ready PR against the default branch with
`Closes #<n>` in its body ([the call](references/rest-calls.md#opening-the-pr)). Check
the reply's `base:` and `draft: false`; record `pr-created`. Never turn on Auto-fix for
it ([why](references/cloud-host.md#auto-fix-stays-off)).

### 5. Wait for the review

Run `review_watch.py <pr>` and act on its verdict; triage every `F<n>`, fix the accepted
ones, and push ([how](references/review-ci-merge.md#the-review)). **After every push,
run it again** and triage any `F<n>` not yet triaged: the review can come more than
once, and the watch appends a later one's findings and names it on `later_review:`.
`NO_REVIEW`, or `ERROR` after one re-run, holds the PR and stops the run. Record
`review`.

### 6. Read CI

Read the check runs and the combined status for the current head
([the call](references/rest-calls.md#the-ci-verdict)). `PASS` → step 7. `FAIL` →
repair, at most 3 times. `PENDING` past 1800 s, or `EMPTY` 600 s after the push
(no checks at all), → stop and ask
([the table](references/review-ci-merge.md#ci)). Record `ci`.

### 7. Merge

Right before the merge, read the review once more with `--timeout 0` and triage
anything new; never merge past a posted, untriaged finding, and never wait on a later
review that is not shown ([how](references/review-ci-merge.md#a-later-review)). Then
squash-merge pinned to the head CI passed
([the call](references/rest-calls.md#the-merge)). 409 → steps 5 and 6 for the new head,
never the old `sha` again; 405 → [the table](references/review-ci-merge.md#the-merge).
Confirm the issue is `closed`; record `merged`.

### 8. Bring the branch up to date and clear what the merge unblocked

`git merge origin/<default>` into the session's branch and check its diff is empty —
never a reset and force-push
([branch upkeep](references/review-ci-merge.md#branch-upkeep-after-the-merge)). Fetch
the backlog again and remove `blocked: dependency` from each issue whose last open
dependency was this one
([the calls](references/rest-calls.md#issues-the-merge-unblocked)).

### 9. File the follow-ups

A sibling of the defect being fixed, found before the merge, is fixed inline in the
open diff; a real, separate defect is filed; a restatement or a speculation is not. **BACKGROUND:** `shipping-issues`, whose reference
on filing follow-ups holds the long form. Verify the defect against the code first. The
body meets `triaging-issues` and ends with the ship contract; the labels are a type
label, a `priority:` tier, and `blocked: dependency` or `blocked: design` when they
apply, each checked to exist first
([the calls](references/rest-calls.md#a-follow-up-issue)). File right after the merge
that surfaced it; record `followup`.

### 10. All mode

Ship one issue at a time: after each merge, fetch the backlog again and rank afresh
(step 2), then start step 3 from the up-to-date branch, without pausing. Once an issue
has a commit on the branch it either merges or stops the run, since the branch cannot
carry two issues' work. An issue that fails before its first commit is skipped, with
the reason, and so is anything depending on it.

### 11. Report

No prescribed format, but never omit
[these facts](references/review-ci-merge.md#what-the-report-must-not-omit) — above all
an issue left open behind a merged PR, a criterion shipped `not-met`, and a PR left
held.

## Stop conditions

Stop the run and report when:

- a REST call answers 403 for GraphQL or repository scope, or a push or every call
  fails the same way after a retry ([cloud-host.md](references/cloud-host.md));
- the digest selects nothing, or the named issue is not ready;
- a PR is held: `NO_REVIEW`, a review `ERROR`, a finding that needs the owner, CI
  pending past 1800 s, no checks at all (`NO_CHECKS`), a fourth CI `FAIL`, or a merge
  refused for a reason other than a moved head;
- the merged issue is still open, or the PR's base or `Closes #<n>` is wrong — this
  skill edits no PR and closes no issue;
- a conflict needs a product decision, or a design question has no answer in the thread;
- the checkout, the branch, or the default branch changed in a way this run did not
  make: leave it exactly as found and ask.

Record before stopping (`--event blocked --field reason=<...>`).

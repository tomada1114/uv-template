# Review, CI and landing for one PR

## Pin each observation to a diff

Record repository, issue, PR URL/number, full head SHA, base SHA/ref and compared diff.
Refresh head/base whenever assessing review or CI. A changed head or base that changes
the diff invalidates earlier verdicts. Record review completion IDs and commit identity,
check names, run URLs and conclusions separately; green CI is not review evidence.

## Observe the opening review

Discover connected review and PR actions. Read submitted reviews, inline threads,
resolution state, PR conversation and task metadata where available. Follow MCP
pagination or discover another MCP action when normalized responses omit data.
If required evidence remains unavailable, report it; never use `gh` or direct HTTP.

If the user or repository records automatic Codex review only on opening, open a regular
PR and observe that initial run. Record opening time, head/base and review activity.
Do not post an explicit request while that automatic run is active, or interpret the
initial delay as failure. This is a run-specific setup, not a universal Codex default.
Do not change review settings or close/reopen the PR to trigger another run.

A terminal result must come from the trusted Codex integration and identify the reviewed
current diff. Read all findings. A display name, acknowledgement, queued task, reaction,
green CI, silence or local review is insufficient. If a no-findings result is delivered
as a conversation comment, verify its trusted author, terminal meaning and associated
head/diff through available task/review metadata; do not infer identity from timing.
If that association cannot be established, report review evidence as unavailable.

Classify findings as accepted, rejected or out of scope with reasons. Fix accepted
in-scope findings, run affected and required gates, commit with hooks and push normally.
Get fresh CI and review for the new diff. Do not assume a push repeats an opening-only
automatic review; resolved threads alone do not prove the new diff reviewed.

When fresh review is needed, check for an active run first. Post `@codex review` only
within the recorded review-comment authorization, including full head SHA and base.
Record request/comment ID and time; never duplicate an active request or use
`@codex fix`. If comment authorization is missing, ask for that scope while continuing
independent CI inspection. Do not replace unavailable cloud review with local review.

## Observe CI alongside review

Inspect workflows and required checks for the current head, including job/step results
and pagination. The committed ruleset and workflows describe expected checks; read live
branch rules to establish enforced requirements and approvals. If live policy cannot
be established, report it as unverified and do not merge on assumptions.

A single green check, earlier SHA, branch name or partial response cannot prove success.
Distinguish successful, failed, pending, skipped, cancelled and inaccessible checks.
A skipped required check is not success unless active policy explicitly permits it.
Diagnose failures while review is pending; corrections start a new evidence phase.
Retries must be authorized and remain associated with their actual head and run.
Never dispatch workflows or change security/settings just to obtain missing evidence.

Use bounded observations (at most 60 seconds per blocking wait) with backoff when state
is unchanged. Keep independent review and CI records; either can finish first. Continue
in-scope repairs without a fixed retry count. A pending gate or elapsed time alone is
not a failure or completion. Honor explicit deadlines and host limits; report required
unavailable evidence precisely and preserve the PR. Once all gates pass, no extra
settling delay is required.

## Land only within the recorded authorization

At a PR-only boundary, preserve the open PR after verified review and CI. Otherwise:

1. Refresh PR head/base, mergeability, review findings/threads, required approvals and
   all expected checks. Confirm acceptance and local verification still cover the diff.
   If base integration is necessary, merge the current default branch normally in the
   issue worktree, then repeat affected gates and obtain fresh review/CI. No force push.
2. Merge with the connector's expected-head-SHA guard and an allowed merge method.
   Never use an admin bypass. If the head changes or merge is rejected, inspect the
   new state before trying again; do not route around a policy rejection.
3. Fetch the PR again and verify merged state, target branch and merge commit. Fetch
   the issue and confirm it closed. If closure failed, close it only within explicit
   issue-closure scope; otherwise report the remaining open issue. A successful write
   response alone is not verification.
4. Preserve the primary checkout and run-owned evidence. Perform only authorized
   cleanup through the matching local or host-managed lifecycle and verify outcomes.

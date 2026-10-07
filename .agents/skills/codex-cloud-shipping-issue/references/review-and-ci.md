# Review and CI evidence for one draft PR

## Pin each observation to a diff

Record the repository, issue, PR URL and number, full PR head SHA, base SHA/ref, and
the compared diff. Refresh the PR head and base whenever checking a review or CI result.
A push or a base change that changes the diff starts a new evidence phase; the previous
review and checks are stale for completion purposes.

## Inspect Codex review

Discover the connected GitHub app's available review and PR actions before using them.
Prefer a connected action when it can read the required data; use `gh` only after its
harmless reads succeed. Read submitted reviews, inline threads, resolution state, PR
conversation, and task metadata where the available actions expose them.

Treat a review as complete only when it is terminal, from the trusted Codex integration,
and tied to the current PR diff. A display name, request acknowledgement, queued task,
reaction, green CI, silence, or local self-review is not terminal review evidence. Read
all findings; record which are accepted, rejected, or out of scope and why. Fix accepted
findings within the issue, then get fresh review and CI evidence for the new head.

Posting `@codex review` is a GitHub write. Do so only when the user's current request
explicitly authorizes a review request. Include the recorded current head SHA and base;
do not duplicate an active request, ask for `@codex fix`, or change review settings.
Without a terminal review result, report review as pending or inaccessible.

## Inspect current-head CI

Read the workflow runs and required checks for the current PR head. Inspect job and step
results, following pagination when the API exposes it. Do not infer a complete green run
from one green check, an earlier SHA, a branch name, or an endpoint that returns only a
partial first page. Compare results with the repository's declared required checks; if
the live required-check set cannot be read, report it as unverified.

Diagnose failures while review is pending. A retry's terminal success applies only to
the same diff; retain enough run information to distinguish a retry from a changed-head
result. Report success, failure, pending, skipped, cancelled, and inaccessible states
separately. A skipped required check is not success unless the repository's active rule
explicitly allows it.

Never dispatch a workflow, change a ruleset, or mark the draft ready to obtain missing
evidence. This workflow stops at the draft PR even when review and CI are green; merge
requires a separate user request and the applicable repository workflow.

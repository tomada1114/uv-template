# Review, CI, merge, and the branch afterwards

The detail behind [SKILL.md steps 5–8](../SKILL.md#5-wait-for-the-review): from an open
PR to a merged one, a closed issue, and the session's branch ready for the next issue.
The REST spelling of each call is in [rest-calls.md](rest-calls.md).

## Table of Contents

- [The review](#the-review)
- [A later review](#a-later-review)
- [CI](#ci)
- [The merge](#the-merge)
- [Branch upkeep after the merge](#branch-upkeep-after-the-merge)
- [What the report must not omit](#what-the-report-must-not-omit)

## The review

Opening a ready PR starts the Codex GitHub integration's review; this run never asks for
one: no `@codex review` comment, no close and reopen, no reply to or resolution of a
review thread. `review_watch.py` reads it over REST alone and says what it saw; its
docstring holds the verdicts, the opening-review memory, and the `later_review:` line.

```bash
mkdir -p <runstate>/review
python3 .agents/skills/shipping-issues/scripts/review_watch.py <pr> --timeout 540 > <runstate>/review/<pr>.log
grep -E '^(verdict|trigger|review_status|reviewed_sha|head_sha|reviewed_is_head|completed_at|later_review|pr_age_seconds|findings|findings_file|detail):|^  - F' <runstate>/review/<pr>.log
```

Run it in the foreground with the call's timeout raised to 600000 ms. If the session is
woken by PR activity meanwhile, that is a cue to run the script again, never a verdict.

| `verdict:` | Next |
| --- | --- |
| `CLEAN` | Nothing to fix; go to CI. |
| `FINDINGS` | Triage every `F<n>` (below), fix the accepted ones, verify, commit, push, then run the watch again before CI. |
| `PENDING_TIMEOUT` | Run the same call again. Past 1800 s of `pr_age_seconds:` with the review still running, treat it as `ERROR`. |
| `NO_REVIEW` | The PR is held: open, unmerged, and the run stops (the branch is the next issue's too). Never a local review instead. |
| `ERROR` | Read `detail:`. An unreadable read: run once more. Anything else holds the PR as for `NO_REVIEW`. |

**Triage.** Read each finding's body in the file `findings_file:` names, never in the
PR conversation, and classify every one, each with a one-line reason that holds against
the code: **accepted** (real, and part of this issue's change), **rejected** (wrong on
reading the code), or **out of scope** (real, not this diff's: step 9). A finding that
needs an owner's decision, or that this session cannot settle either way, holds the
PR. **BACKGROUND:** `shipping-issues`, whose reference on triaging the review's
findings is the long form of these rules. Write the ledger as you go, one line per
finding, to `<runstate>/review/<pr>-triage.md`:
`F<n> id=<comment id> accepted|rejected|out-of-scope — <reason> — fixed-in <sha>`.

**After every push** — a fix, a CI repair, or bringing the branch up to date — run
`review_watch.py <pr>` again, into the same log. Once it has seen the opening review
complete it answers at once, with the same verdict and the same `F<n>` numbers, a new
finding appended after the old ones. Triage every `F<n>` whose `id=` is not in the
ledger, and read `later_review:`. Then watch CI for the new head.

## A later review

The review can run more than once on a PR: after a push, a second review may post more
findings. The summary comment keeps one row, rewritten for the latest review, so the
watch keeps the opening verdict in `<runstate>/review/<pr>-opening.json` and names the
later one on `later_review:`. Its findings, as they are posted, are listed with the
rest.

Right before the merge, once CI is `PASS` for the head being merged, read the review
one last time:

```bash
python3 .agents/skills/shipping-issues/scripts/review_watch.py <pr> --timeout 0 > <runstate>/review/<pr>.log
```

- Any `F<n>` not in the ledger is triaged now. An accepted one is fixed, verified, and
  pushed, and the PR goes back through the review re-read and CI for the new head.
- `later_review:` showing a review that has not completed: re-read once a minute, 8
  reads at most (one foreground call, its timeout raised to 600000 ms), triage
  what it lists, then merge on what is posted, and name in the report a later review
  still running at the merge:

  ```bash
  for read in $(seq 1 8); do
    python3 .agents/skills/shipping-issues/scripts/review_watch.py <pr> --timeout 0 > <runstate>/review/<pr>.log
    grep -Eiq '^later_review: (none|.*(complete|fail|error|cancel))' <runstate>/review/<pr>.log && break
    sleep 60
  done; grep -E '^(verdict|later_review|findings):|^  - F' <runstate>/review/<pr>.log
  ```

- `later_review: none`, or a completed one whose findings are all in the ledger: merge.

Never wait for a later review that is not shown, and never merge past a finding that is
already posted and untriaged. A resumed run on a fresh VM has lost
`<pr>-opening.json`: the watch then waits for whatever review the summary shows to
complete, and the 1800 s cap above still holds.

## CI

Read CI only for the head the last push produced, with the call in
[rest-calls.md](rest-calls.md#the-ci-verdict), into `<runstate>/ci/<pr>.log`.

| Last `verdict:` | Next |
| --- | --- |
| `PASS` | The [pre-merge review read](#a-later-review), then the merge, in the same turn. |
| `FAIL` | Repair: reproduce with the matching local command ([a failing check](rest-calls.md#a-failing-check)), fix, `just verify`, commit, push, re-run the review watch, read CI again. At most 3 repairs per issue; a fourth `FAIL` stops the run. |
| `PENDING` | Run the call again. Past 1800 s of reads for one head, the PR is held and the run stops. |
| `EMPTY` | Run the call again: check runs appear a little after a push. Still `EMPTY` 600 s after the push, there are no checks at all (`NO_CHECKS`): stop and ask the owner. |
| `ERROR` | Run the call once more; a second `ERROR` is a stop, reported with the message. |

A test deleted, skipped, or weakened to get a `PASS`, or a re-run without a diagnosis,
is a failed repair, not a green one.

## The merge

Merge as soon as the review has settled and the pre-merge read is clean, with CI `PASS`
for the head being merged: no "shall I merge?", no summary-then-wait. The call pins the
merge to that head ([rest-calls.md](rest-calls.md#the-merge)).

| Reply | Next |
| --- | --- |
| 200, `merged: true` | Read the issue. `closed` → done; record it. Still `open` → read again after 10 s; still open → the run stops and asks the owner: this skill closes no issue by hand. |
| 409 | The head moved after the CI read. Re-run the review watch and CI for the new head; never retry with the old `sha`. |
| 405 | Read the PR. `mergeable: false` is a conflict: [bring the branch up to date](#branch-upkeep-after-the-merge) with `origin/<default>`, resolve a mechanical conflict, `just verify`, push, then the review watch and CI again. A conflict that needs a product decision, or a 405 with `mergeable: true` (a required review or rule), holds the PR: stop and ask. `null` → read again. |
| 403 | [A 403 from the proxy](cloud-host.md#a-403-from-the-proxy), or no merge permission: stop and report. |
| anything else | Read the PR: only `merged: true` is a merge. Report the reply and stop. |

Then, in the same turn: record the merge, clear the labels of the
[issues the merge unblocked](rest-calls.md#issues-the-merge-unblocked), and file the
follow-ups this PR surfaced (step 9).

## Branch upkeep after the merge

The session's branch carries the issue's own commits; the default branch now carries
their squash. Bring the branch up to date by merging, never by a reset or a rebase
followed by a force-push:

```bash
git fetch origin <default> --quiet
git merge --no-edit origin/<default>
git diff --stat origin/<default>      # must print nothing
```

The merge is clean, because both sides made the same change. An empty diff proves the
branch's tree is the default branch's. Anything else is work that is not on the default
branch: stop and ask. Then:

- **`delete_branch_on_merge: true`** — GitHub deleted the remote branch; the next
  `git push -u origin <branch>` creates it afresh.
- **`false`** — the remote branch still points at the merged head, which the local
  branch now descends from; the next push is a fast-forward.

Git counts the pre-squash commits as not on the default branch, so they may be listed
among the next PR's commits; its diff, which the review reads and the squash takes, is
the new work alone. `git reflog` on the branch shows no forced update at any point.

## What the report must not omit

No prescribed format, but each of these is a fact whose absence changes what the reader
believes happened. **BACKGROUND:** `shipping-issues`, whose closing-out reference is
the long form.

- Any issue left open behind a merged PR — stated, never implied.
- Per PR: the review's verdict and `reviewed_sha:`, every finding with its
  classification and reason, the commit that fixed the accepted ones, any later review
  and whether it had completed at the merge, and that fixes after the review were
  covered by local verification and current-head CI. A held PR is named as held, open.
- Acceptance criteria that shipped `not-met`, and why; or that all were met; or that the
  issue carried none.
- Follow-ups filed with their URLs and labels, what was fixed inline instead, findings
  checked and deliberately not filed, and a label the reply did not echo back.
- Issues that ranked on a suggested `~P<n>` tier (no label written), and stale
  dependency labels left for a human.
- Everything held, stopped, or skipped, with the reason — and the state of the
  session's branch when the run stopped (`git log --oneline origin/<default>..HEAD`).
- Operator actions the run surfaced, such as reconnecting GitHub, clearing Auto-fix, or
  running `just labels`.

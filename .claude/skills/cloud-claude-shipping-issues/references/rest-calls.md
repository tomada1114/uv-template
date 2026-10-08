# The REST calls

Every GitHub read and write this skill makes, spelled as a `gh api` call. Run them from
the checkout's root ([how `{owner}/{repo}` resolves](cloud-host.md#how-github-is-reached)).
A built-in GitHub tool that performs the same REST operation may stand in for a call;
nothing else may. Never `gh pr`, `gh issue`, `gh repo view`, `gh label list`,
`gh api graphql`, or `search/issues`: the proxy refuses each
([a 403 from the proxy](cloud-host.md#a-403-from-the-proxy)).

`<runstate>` is `${AGENT_SKILL_STATE_DIR:-$HOME/.local/state/agent-skills}/shipping-issues/<owner>__<repo>`,
the directory `review_watch.py` keeps its memory in. Request and response files go there,
never inside the checkout.

## Table of Contents

- [The repository](#the-repository)
- [The backlog and the pick](#the-backlog-and-the-pick)
- [One issue](#one-issue)
- [Opening the PR](#opening-the-pr)
- [Reading the PR](#reading-the-pr)
- [The CI verdict](#the-ci-verdict)
- [A failing check](#a-failing-check)
- [The merge](#the-merge)
- [Issues the merge unblocked](#issues-the-merge-unblocked)
- [A follow-up issue](#a-follow-up-issue)

## The repository

```bash
gh api repos/{owner}/{repo} \
  --jq '"repo: \(.full_name)\ndefault: \(.default_branch)\ndelete_branch_on_merge: \(.delete_branch_on_merge)\nallow_squash_merge: \(.allow_squash_merge)"'
```

`full_name`, `default_branch`, `delete_branch_on_merge` and `allow_squash_merge` are
fields of the repository object
([get a repository](https://docs.github.com/en/rest/repos/repos#get-a-repository),
checked 2026-10-07). `allow_squash_merge: false` is a stop: this skill merges by squash
only.

## The backlog and the pick

```bash
mkdir -p <runstate>/rest
gh api --paginate --slurp "repos/{owner}/{repo}/issues?state=open&per_page=100" > <runstate>/rest/issues.json
gh api --paginate --slurp "repos/{owner}/{repo}/pulls?state=open&per_page=100" > <runstate>/rest/pulls.json
python3 .agents/skills/shipping-issues/scripts/issue_digest.py --issues-file <runstate>/rest/issues.json \
    --prs-file <runstate>/rest/pulls.json --select 3 --with-rank --detail-top 1 --body-chars 700
```

The issues endpoint lists pull requests too, each marked by a `pull_request` key
([list repository issues](https://docs.github.com/en/rest/issues/issues#list-repository-issues),
checked 2026-10-07); the digest drops them. Both files are required together, and file
mode takes no `--label`, `--assignee`, or `--milestone` (exit 2); it ranks at most
`--limit` issues (default 200), so pass `--limit 1000` on a larger backlog. A named
issue: add `--issue <n> --detail <n>` — naming it lifts only the design hold. Read
`select:`, `next:`, `held:`, `needs-design:`, `tracking:` and the `labels:` line as the
digest's own docstring describes them; `~P<n>` is a suggested tier.

Fetch both files again, never reuse them, after any merge or filing: the digest's
picture is only as fresh as the files.

## One issue

```bash
gh api repos/{owner}/{repo}/issues/<n> --jq '"#\(.number) \(.state) \(.title)\nlabels: \([.labels[].name] | join(", "))\n\n\(.body)"'
gh api --paginate repos/{owner}/{repo}/issues/<n>/comments --jq '.[] | "--- \(.user.login) \(.created_at)\n\(.body)"'
```

Read the body and every comment before the acceptance map. A dependency named in the
body is read the same way, for its `state`.

## Opening the PR

Write the body to `<runstate>/pr/<n>-body.md` from `.github/PULL_REQUEST_TEMPLATE.md`:
the summary, then **`Closes #<n>`** on its own line, then the test plan and the
checklist, each ticked only when true. Then:

```bash
gh api -X POST repos/{owner}/{repo}/pulls -f title='<conventional-commit title>' \
  -f head=<branch> -f base=<default> -F body=@<runstate>/pr/<n>-body.md \
  --jq '"pr: \(.number)\nurl: \(.html_url)\nhead_sha: \(.head.sha)\nbase: \(.base.ref)\ndraft: \(.draft)"'
```

Leaving out `draft` creates the PR ready
([create a pull request](https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request),
checked 2026-10-07), and only a ready PR gets the opening Codex review
(`review_watch.py`'s docstring). Check the reply: `base:` is the default branch and `draft: false`.
A 422 that says a pull request already exists for the branch: list it with
`gh api "repos/{owner}/{repo}/pulls?head=<owner>:<branch>&state=open" --jq '.[] | "\(.number) \(.title)"'`.
One this run opened for the same issue is the PR to continue; anything else is a stop.

## Reading the PR

```bash
gh api repos/{owner}/{repo}/pulls/<pr> \
  --jq '"state: \(.state)\nmerged: \(.merged)\ndraft: \(.draft)\nhead_sha: \(.head.sha)\nbase: \(.base.ref)\nmergeable: \(.mergeable)\nmergeable_state: \(.mergeable_state)\ncloses: \((.body // "") | test("(?i)(close[sd]?|fix(e[sd])?|resolve[sd]?):? +#<n>\\b"))"'
```

`mergeable` is `true` or `false` once GitHub has computed it and `null` while it is
still computing; read again after a few seconds
([get a pull request](https://docs.github.com/en/rest/pulls/pulls#get-a-pull-request),
checked 2026-10-07). `closes: false` or a `base:` other than the default branch means
the merge would leave the issue open: this run does not edit a PR, so that is a stop
for this issue (ask the owner).

## The CI verdict

One foreground call reads the head commit's check runs and its combined status every 30
s, for at most 16 reads (about 8 minutes), and stops at the first `PASS`, `FAIL`, or
`ERROR`. Raise the call's own timeout to 600000 ms. Repeat the call on `PENDING` or
`EMPTY`; the step's caps are in [review-ci-merge.md](review-ci-merge.md#ci).

```bash
sha=<head_sha>; log=<runstate>/ci/<pr>.log; mkdir -p "${log%/*}"
for read in $(seq 1 16); do
  runs=$(gh api --paginate "repos/{owner}/{repo}/commits/$sha/check-runs?per_page=100" \
    --jq '.check_runs[] | [.status, (.conclusion // "none"), .name] | @tsv') \
    || { echo "verdict: ERROR check runs unreadable"; break; }
  combined=$(gh api "repos/{owner}/{repo}/commits/$sha/status" \
    --jq '[.state, .total_count] | @tsv') \
    || { echo "verdict: ERROR combined status unreadable"; break; }
  verdict=$(printf '%s\n%s\n' "$combined" "$runs" | awk -F'\t' '
    NR == 1 { state = $1; statuses = $2 + 0; next }
    NF < 3 { next }
    { runs++ }
    $1 != "completed" { pending++; next }
    $2 ~ /^(success|neutral|skipped)$/ { next }
    $2 ~ /^(failure|cancelled|timed_out|action_required|startup_failure)$/ {
      failed++; print "failed_check: " $3 > "/dev/stderr"; next }
    { pending++ }
    END {
      if (failed || state == "failure") print "FAIL"
      else if (runs + statuses == 0) print "EMPTY"
      else if (pending || (statuses > 0 && state != "success")) print "PENDING"
      else print "PASS"
    }')
  echo "verdict: $verdict head_sha: $sha read: $read at: $(date -u +%FT%TZ)"
  case $verdict in PASS|FAIL) break ;; esac
  sleep 30
done >> "$log" 2>&1; tail -n 3 "$log"
```

The rule it applies: **PASS** when every check run is `completed` with `success`,
`neutral`, or `skipped`, and the combined status is `success` or counts no status at
all; **FAIL** on a check run concluding `failure`, `cancelled`, `timed_out`,
`action_required`, or `startup_failure`, or a combined status of `failure`; **EMPTY**
when there is neither a check run nor a status; anything else is **PENDING**. Check-run
statuses and conclusions are the enums of
[list check runs for a Git reference](https://docs.github.com/en/rest/checks/runs#list-check-runs-for-a-git-reference),
and the combined state is `pending` when there are no statuses at all, which is why a
zero count is not a failure
([combined status](https://docs.github.com/en/rest/commits/statuses#get-the-combined-status-for-a-specific-reference),
both checked 2026-10-07). Reading by the head SHA, never by branch, keeps a previous
commit's results out of the verdict.

## A failing check

```bash
gh api "repos/{owner}/{repo}/commits/<sha>/check-runs?per_page=100" \
  --jq '.check_runs[] | select(.conclusion == "failure" or .conclusion == "timed_out") | "\(.name)\t\(.html_url)"'
```

Reproduce the failure with the matching local command first — CI runs the checks of
`just verify` (AGENTS.md "Enforcement layers"). A job's log is
`GET repos/{owner}/{repo}/actions/jobs/<job_id>/logs`, a redirect to a short-lived
download URL ([download job logs](https://docs.github.com/en/rest/actions/workflow-jobs#download-job-logs-for-a-workflow-run),
checked 2026-10-07); the job ids come from
`gh api "repos/{owner}/{repo}/actions/runs?head_sha=<sha>" --jq '.workflow_runs[] | "\(.id) \(.name) \(.conclusion)"'`
and `gh api repos/{owner}/{repo}/actions/runs/<run_id>/jobs --jq '.jobs[] | "\(.id) \(.name) \(.conclusion)"'`.
Redirect a log to `<runstate>/ci/` and read its tail, never the whole log.

## The merge

```bash
gh api -X PUT repos/{owner}/{repo}/pulls/<pr>/merge -f merge_method=squash -f sha=<head_sha> \
  --jq '"merged: \(.merged)\nsha: \(.sha)"'
```

`<head_sha>` is the SHA the `PASS` was read for. GitHub merges only when the PR's head
still matches it; the replies that matter are 200 merged, 405 the merge cannot be
performed, and 409 the head no longer matches the `sha`
([merge a pull request](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request),
checked 2026-10-07). `gh` exits non-zero and prints `HTTP 405` or `HTTP 409` on the
latter two. What each one means for the run:
[review-ci-merge.md](review-ci-merge.md#the-merge).

Then the issue:

```bash
gh api repos/{owner}/{repo}/issues/<n> --jq '"issue: \(.state) \(.state_reason // "")"'
```

## Issues the merge unblocked

After the merge, fetch the backlog again ([above](#the-backlog-and-the-pick)), then:

```bash
python3 .agents/skills/shipping-issues/scripts/issue_digest.py --issues-file <runstate>/rest/issues.json \
    --prs-file <runstate>/rest/pulls.json --json --body-chars 0 \
  | python3 -c 'import json, sys; n = int(sys.argv[1]); print(" ".join(str(i["number"]) for i in json.load(sys.stdin)["issues"] if n in i["depends_on"] and "blocked: dependency" in i["stale_dependency_labels"]))' <n>
```

It prints the open issues that record a dependency on `#<n>`, still carry
`blocked: dependency`, and have no open dependency left. For each:

```bash
gh api -X DELETE "repos/{owner}/{repo}/issues/<m>/labels/blocked%3A%20dependency" --jq '[.[].name] | join(", ")'
```

([remove a label from an issue](https://docs.github.com/en/rest/issues/labels#remove-a-label-from-an-issue),
checked 2026-10-07). A stale label on an issue that does not depend on `#<n>`, or a
recognized equivalent spelled differently, is not this merge's to clear: list it in the
report.

## A follow-up issue

Every label the issue needs is checked first; a missing one stops the filing, since
creating a label definition (`just labels`) is not in this skill's sign-off:

```bash
gh api "repos/{owner}/{repo}/labels/priority%3A%20P2" --jq .name   # one call per label
```

The body file `<runstate>/followups/<slug>.md` holds what `triaging-issues` asks of a
body, then — exactly as `shipping-issues`' `file_followup.py` would have written them —
a `## Dependencies` section with one `Depends on: #N` line per blocker (only when there
is one), the line `*Found while shipping #<n>.*` after a `---` rule, and the ship
contract as the last line:
`<!-- ship: tier=P2 area=<area> blocked-by=none touches=<paths or *> design=settled -->`.
Then:

```bash
gh api -X POST repos/{owner}/{repo}/issues -f title='<title>' \
  -F body=@<runstate>/followups/<slug>.md \
  -f 'labels[]=<type label>' -f 'labels[]=priority: P2' \
  --jq '"filed: \(.html_url)\nlabels: \([.labels[].name] | join(", "))"'
```

Add `-f 'labels[]=blocked: dependency'` with a `Depends on:` line, and
`-f 'labels[]=blocked: design'` with `design=open`. GitHub drops labels without an
error when the caller lacks push access
([create an issue](https://docs.github.com/en/rest/issues/issues#create-an-issue),
checked 2026-10-07), so compare the reply's `labels:` with what was sent; a difference is
a report line, never a second write.

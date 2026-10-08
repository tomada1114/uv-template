#!/usr/bin/env python3
"""review_watch.py — Wait for a PR's automatic opening review and report it.

The pull request's review is the Codex GitHub integration's, posted by the
bot account `chatgpt-codex-connector[bot]`. About 15 s after a PR opens, the bot
posts one issue comment carrying the marker
`<!-- codex-pull-request-review-summary -->` and edits it in place: its table
row holds the review's status (`🔄 **Running**`, then `✅ **Completed**`, each
with a `<relative-time datetime=...>`), the 7-character short commit it
reviewed, and its trigger ("PR opened"). Running to Completed took about
2.5 minutes on PRs #170 and #171 (observed 2026-10-07). Findings arrive as a
COMMENTED review from the bot (`commit_id` = the reviewed commit) with inline
comments, each starting with a priority badge (`![P1 Badge]`, P0, P2, ...) and
a bold title. A clean review leaves no review and no inline comment; the bot
reacts 👍 on the PR, which this script reports as corroboration only.

The summary keeps one row, rewritten for the latest review: after an
`@codex review` comment it reads `Manual request` and the opening row is gone
(PRs #154 and #156, observed 2026-10-07). So once this script sees the opening
review ("PR opened") complete, it remembers that row in
<runstate>/review/<pr>-opening.json, and a later, unsolicited review never
replaces that verdict: it is reported on `later_review:`, and any finding it
already posted is still listed. Without that memory, a later row settles only
once it is Completed itself.

This script only reads. It never asks for a review: no `@codex review`
comment, no close/reopen, no reply to or resolution of a thread. A push does
not start a new review, so the one review this waits for is the opening one.

Usage:
    review_watch.py <pr-number> [--timeout SECONDS] [--bot LOGIN]
                    [--grace SECONDS] [--interval SECONDS]
                    [--findings-file PATH]

  --timeout  how long this call waits, in bounded polls (default 900). Run it
             in the background where the host reports completion, or in
             foreground slices under the host's command timeout; each slice
             re-reads the PR from scratch.
  --grace    how long after the PR opened silence from the bot means it is
             not coming (default 900): NO_REVIEW. Measured from the PR's own
             creation time, so slices add up without the caller counting.
  --bot      the trusted reviewer login (default chatgpt-codex-connector[bot]).
             Only a comment, review or reaction by exactly this login counts
             (a login without `[bot]` must also have account type Bot); a
             display name, or a person quoting the marker, never does.
  --interval seconds between polls (default 30).
  --findings-file  where finding bodies are written (default
             <runstate>/review/<pr>-findings.md, outside any checkout).

Prints:
  verdict: CLEAN | FINDINGS | PENDING_TIMEOUT | NO_REVIEW | ERROR
  pr: <number>
  bot: <login>
  review_status: <the summary's status, e.g. Completed> | none
  trigger: <the summary's review trigger> | none
  reviewed_sha: <the commit the review read> | none
  head_sha: <the PR's head now> | none
  reviewed_is_head: yes | no   (no after a fix push: still that review's
                    verdict — a push starts no new review)
  completed_at: <the summary's completion time> | none   (compare it with
                    the merge time: a review that completed after the merge
                    is a step 10 line)
  thumbs_up: yes | no
  later_review: <status> (<trigger>) | none   (a review after the opening one)
  pr_age_seconds / waited_seconds
  findings: <n>, then one line per finding:
    - F<n> [P<k>] <path>:<line> id=<comment id> — <title>
  findings_file: <path>   (when findings > 0; bodies stay out of this output)
  detail: <why>           (for every verdict but CLEAN and FINDINGS)

  CLEAN     the summary says Completed for a commit of this PR and the bot
            left no review and no inline comment (`thumbs_up:` corroborates;
            neither its presence nor its absence decides the verdict).
  FINDINGS  the summary says Completed and the bot left findings; triage
            every one.
  PENDING_TIMEOUT  this call's wait ended first: not posted yet, or still
            running. Run it again; `pr_age_seconds` says how long the PR has
            waited.
  NO_REVIEW no trace of the bot `--grace` seconds after the PR opened.
  ERROR     the review failed or was cancelled, the summary names a commit
            that is not on this PR, the PR is a draft (never reviewed), or
            GitHub could not be read. Never a pass.

Exit codes: 0 = CLEAN, 1 = FINDINGS, 2 = PENDING_TIMEOUT, 3 = NO_REVIEW,
            4 = usage/lookup error or ERROR
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_BOT = "chatgpt-codex-connector[bot]"
SUMMARY_MARKER = "<!-- codex-pull-request-review-summary -->"
SKILL_STATE_NAME = "shipping-issues"

EXIT = {"CLEAN": 0, "FINDINGS": 1, "PENDING_TIMEOUT": 2, "NO_REVIEW": 3,
        "ERROR": 4}

FAILED_WORDS = ("fail", "error", "cancel", "timed out", "timeout", "skip",
                "abort")
BADGE_RE = re.compile(r"!\[(P\d) Badge\]")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
SHA_CELL_RE = re.compile(r"`([0-9a-fA-F]{7,40})`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
DATETIME_RE = re.compile(r'datetime="([^"]+)"')


class ReadError(Exception):
    """A gh read failed; the poll that hit it decides nothing."""


class PrUnreadableError(ReadError):
    """The PR itself could not be read."""


def gh(args: list[str]) -> str:
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True,
                              timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        msg = f"gh {' '.join(args[:3])}: {exc}"
        raise ReadError(msg)
    if proc.returncode != 0:
        err = " ".join((proc.stderr or "").split())
        msg = f"gh {' '.join(args[:3])} exited {proc.returncode}" + (f": {err}" if err else "")
        raise ReadError(msg)
    return proc.stdout or ""


def gh_items(path: str) -> list[dict]:
    """Every item of a paginated REST list, one JSON object per line."""
    out = gh(["api", path, "--paginate", "-q", ".[] | @json"])
    items = []
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except ValueError:
            msg = f"unreadable JSON from {path}"
            raise ReadError(msg)
        if isinstance(item, dict):
            items.append(item)
    return items


def read_pr(pr: str) -> dict:
    """The PR over REST, in the keys `poll` reads (the GraphQL-backed
    `gh pr view` is refused by the Claude Code cloud GitHub proxy)."""
    try:
        out = gh(["api", f"repos/{{owner}}/{{repo}}/pulls/{pr}"])
        data = json.loads(out)
    except ReadError as exc:
        raise PrUnreadableError(str(exc))
    except ValueError:
        msg = f"unreadable JSON for PR #{pr}"
        raise PrUnreadableError(msg)
    if not isinstance(data, dict):
        msg = f"unreadable JSON for PR #{pr}"
        raise PrUnreadableError(msg)
    head = data.get("head")
    if data.get("state") == "open":
        state = "OPEN"
    elif data.get("merged_at"):
        state = "MERGED"
    else:
        state = "CLOSED"
    return {
        "headRefOid": (head.get("sha") if isinstance(head, dict) else None) or "",
        "createdAt": data.get("created_at"),
        "isDraft": bool(data.get("draft")),
        "state": state,
    }


def trusted(item: dict, bot: str) -> bool:
    """Authored by the bot account itself, matched on the exact login.

    A `[bot]` login belongs to a GitHub App alone: a person's login holds only
    letters, digits and hyphens, so it cannot be spoofed. The account type is
    not enough on its own and not always right — the reactions API reports the
    Codex app's 👍 with type "User" (observed on PR #170, 2026-10-07) — so a
    `[bot]` login is trusted on the login, and any other login needs type Bot.
    """
    user = item.get("user") or {}
    if user.get("login") != bot:
        return False
    return bot.endswith("[bot]") or user.get("type") == "Bot"


def pr_age_seconds(created_at: str | None) -> int | None:
    if not created_at:
        return None
    try:
        # strptime rather than fromisoformat: the system python3 may predate
        # 3.11, whose fromisoformat is the first to accept a trailing "Z".
        opened = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0, int(time.time() - opened.timestamp()))


def parse_summary(body: str) -> dict | None:
    """The summary table's code-review row: kind, status, sha, trigger."""
    rows = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        status = BOLD_RE.search(cells[1])
        if not status:
            continue  # the header row or the separator row
        sha = SHA_CELL_RE.search(cells[2])
        when = DATETIME_RE.search(cells[1])
        rows.append({
            "kind": cells[0].replace("*", "").strip(),
            "status": status.group(1).strip(),
            "at": when.group(1) if when else "",
            "sha": sha.group(1).lower() if sha else "",
            "trigger": cells[3] or "none",
        })
    if not rows:
        return None
    for row in rows:
        if "code review" in row["kind"].lower():
            return row
    return rows[0]


def status_class(status: str) -> str:
    lowered = status.lower()
    if "complete" in lowered:
        return "completed"
    if any(word in lowered for word in FAILED_WORDS):
        return "failed"
    return "running"


def finding_title(body: str) -> str:
    first = next((ln for ln in body.splitlines() if ln.strip()), "")
    title = IMAGE_RE.sub("", first)
    title = re.sub(r"</?sub>", "", title).replace("**", "")
    title = " ".join(title.split())
    return (title[:117] + "...") if len(title) > 120 else (title or "(untitled)")


def collect_findings(reviews: list[dict], inline: list[dict]) -> list[dict]:
    """The bot's top-level inline comments, oldest first, plus any bot review
    that carries no inline comment at all (its body is then the finding)."""
    findings = []
    seen_reviews = set()
    for comment in sorted(inline, key=lambda c: c.get("id") or 0):
        if comment.get("in_reply_to_id"):
            continue
        body = comment.get("body") or ""
        badge = BADGE_RE.search(body)
        line = comment.get("line") or comment.get("original_line") or "?"
        seen_reviews.add(comment.get("pull_request_review_id"))
        findings.append({
            "id": str(comment.get("id")),
            "priority": badge.group(1) if badge else "P?",
            "where": f"{comment.get('path') or '?'}:{line}",
            "title": finding_title(body),
            "commit": comment.get("original_commit_id") or comment.get("commit_id") or "",
            "url": comment.get("html_url") or "",
            "body": body,
        })
    for review in sorted(reviews, key=lambda r: r.get("id") or 0):
        if review.get("id") in seen_reviews:
            continue
        if review.get("state") not in ("COMMENTED", "CHANGES_REQUESTED"):
            continue
        findings.append({
            "id": f"review-{review.get('id')}",
            "priority": "P?",
            "where": "-",
            "title": "a review with no inline comment; read its body",
            "commit": review.get("commit_id") or "",
            "url": review.get("html_url") or "",
            "body": review.get("body") or "",
        })
    for number, finding in enumerate(findings, start=1):
        finding["n"] = f"F{number}"
    return findings


_RUNSTATE: list[Path | None] = []


def review_dir() -> Path | None:
    """<runstate>/review for the current repo, resolved once; None if unknown."""
    if not _RUNSTATE:
        try:
            repo = gh(["repo", "view", "--json", "nameWithOwner",
                       "-q", ".nameWithOwner"]).strip()
        except ReadError:
            repo = ""
        _RUNSTATE.append(
            state_dir() / SKILL_STATE_NAME / repo.replace("/", "__") / "review"
            if re.fullmatch(r"[^/\s]+/[^/\s]+", repo) else None)
    return _RUNSTATE[0]


def opening_trigger(trigger: str) -> bool:
    """The automatic review: a PR opened, or a draft marked ready."""
    lowered = trigger.lower()
    return "opened" in lowered or "ready" in lowered


def load_opening(pr: str) -> dict | None:
    folder = review_dir()
    if folder is None:
        return None
    try:
        row = json.loads((folder / f"{pr}-opening.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(row, dict) and row.get("sha") and status_class(row.get("status", "")) == "completed":
        return row
    return None


def save_opening(pr: str, row: dict) -> None:
    folder = review_dir()
    if folder is None:
        return
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{pr}-opening.json").write_text(json.dumps(row), encoding="utf-8")
    except OSError:
        pass  # memory is a convenience; the verdict above stands without it


def poll(pr: str, bot: str, grace: int) -> dict:
    """One full read of the PR's review state. Raises ReadError."""
    data = read_pr(pr)
    head = data.get("headRefOid") or ""
    age = pr_age_seconds(data.get("createdAt"))
    state = {"head": head, "age": age, "summary": None, "findings": [],
             "verdict": None, "detail": "", "thumbs_up": False,
             "reviewed_is_head": None, "later": None}
    if data.get("isDraft"):
        state["verdict"] = "ERROR"
        state["detail"] = (f"PR #{pr} is a draft: Codex reviews a PR when it opens "
                           "ready or is marked ready, never a draft")
        return state

    base = "repos/{owner}/{repo}"
    comments = [c for c in gh_items(f"{base}/issues/{pr}/comments") if trusted(c, bot)]
    reviews = [r for r in gh_items(f"{base}/pulls/{pr}/reviews") if trusted(r, bot)]
    inline = [c for c in gh_items(f"{base}/pulls/{pr}/comments") if trusted(c, bot)]
    reactions = [r for r in gh_items(f"{base}/issues/{pr}/reactions") if trusted(r, bot)]

    summaries = [c for c in comments if SUMMARY_MARKER in (c.get("body") or "")]
    summary = max(summaries, key=lambda c: (c.get("updated_at") or "", c.get("id") or 0),
                  default=None)
    row = parse_summary(summary.get("body") or "") if summary else None
    state["summary"] = row
    state["findings"] = collect_findings(reviews, inline)
    bot_seen = bool(summaries or reviews or inline or reactions)
    state["thumbs_up"] = any(r.get("content") == "+1" for r in reactions)

    if summary is None:
        if not bot_seen and age is not None and age >= grace:
            state["verdict"] = "NO_REVIEW"
            state["detail"] = (f"no comment, review or reaction from {bot} "
                               f"{age}s after PR #{pr} opened (grace {grace}s)")
        else:
            state["detail"] = "the review summary is not posted yet"
        return state
    if row is None:
        state["detail"] = "the review summary has no status row yet"
        return state

    # The row shows the latest review only. A later one (a manual request)
    # never replaces an opening review this watch already saw complete.
    if not opening_trigger(row["trigger"]):
        state["later"] = row
        remembered = load_opening(pr)
        if remembered is not None:
            row = remembered
            state["summary"] = row
        elif status_class(row["status"]) == "running":
            state["detail"] = (f"a later review ({row['trigger']}) is "
                               f"{row['status']!r} and this watch never saw the "
                               "opening review complete, so it waits for that one")
            return state

    kind = status_class(row["status"])
    if kind == "failed":
        state["verdict"] = "ERROR"
        state["detail"] = f"the Codex review reported {row['status']!r}"
        return state
    if kind == "running":
        state["detail"] = f"the Codex review is {row['status']!r}"
        return state

    if not row["sha"]:
        state["verdict"] = "ERROR"
        state["detail"] = "the completed review summary names no reviewed commit"
        return state
    # The short sha is matched against the head first; after a fix push the
    # head has moved on, and the review still speaks for the PR as long as the
    # commit it read is one of the PR's own.
    state["reviewed_is_head"] = head.lower().startswith(row["sha"])
    if not state["reviewed_is_head"]:
        commits = gh(["api", f"{base}/pulls/{pr}/commits", "--paginate",
                      "-q", ".[].sha"]).split()
        if not any(sha.lower().startswith(row["sha"]) for sha in commits):
            state["verdict"] = "ERROR"
            state["detail"] = (f"the summary's reviewed commit {row['sha']} is not "
                               f"a commit of PR #{pr}")
            return state
    state["verdict"] = "FINDINGS" if state["findings"] else "CLEAN"
    if opening_trigger(row["trigger"]):
        save_opening(pr, row)
    return state


def state_dir() -> Path:
    env = os.environ.get("AGENT_SKILL_STATE_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".local" / "state" / "agent-skills"


def default_findings_file(pr: str) -> Path:
    folder = review_dir()
    if folder is not None:
        return folder / f"{pr}-findings.md"
    fd, name = tempfile.mkstemp(prefix=f"review-{pr}-", suffix=".md")
    os.close(fd)
    return Path(name)


def write_findings(path: Path, pr: str, findings: list[dict]) -> None:
    parts = [f"# Review findings for PR #{pr}\n"]
    parts.extend(
        f"## {finding['n']} [{finding['priority']}] {finding['where']} "
        f"id={finding['id']}\n\n"
        f"- title: {finding['title']}\n"
        f"- commit: {finding['commit'] or 'unknown'}\n"
        f"- url: {finding['url'] or 'unknown'}\n\n"
        f"{finding['body'].rstrip()}\n"
        for finding in findings
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def report(verdict: str, args: argparse.Namespace, state: dict | None,
           waited: int, detail: str) -> int:
    state = state or {}
    row = state.get("summary") or {}
    findings = state.get("findings") or []
    age = state.get("age")
    findings_line = ""
    if findings:
        path = Path(args.findings_file) if args.findings_file else default_findings_file(args.pr)
        try:
            write_findings(path, args.pr, findings)
            findings_line = f"findings_file: {path}"
        except OSError as exc:
            findings_line = f"findings_file: unwritten ({exc})"
            if verdict == "FINDINGS":
                verdict = "ERROR"
                detail = f"could not write the findings file {path}"
    print(f"verdict: {verdict}")
    print(f"pr: {args.pr}")
    print(f"bot: {args.bot}")
    print(f"review_status: {row.get('status') or 'none'}")
    print(f"trigger: {row.get('trigger') or 'none'}")
    print(f"reviewed_sha: {row.get('sha') or 'none'}")
    print(f"head_sha: {state.get('head') or 'none'}")
    is_head = state.get("reviewed_is_head")
    print(f"reviewed_is_head: {'none' if is_head is None else ('yes' if is_head else 'no')}")
    completed = row.get("at") if status_class(row.get("status") or "") == "completed" else ""
    print(f"completed_at: {completed or 'none'}")
    print(f"thumbs_up: {'yes' if state.get('thumbs_up') else 'no'}")
    later = state.get("later")
    print(f"later_review: {later['status'] + ' (' + later['trigger'] + ')' if later else 'none'}")
    print(f"pr_age_seconds: {age if age is not None else 'unknown'}")
    print(f"waited_seconds: {waited}")
    print(f"findings: {len(findings)}")
    for finding in findings:
        print(f"  - {finding['n']} [{finding['priority']}] {finding['where']} "
              f"id={finding['id']} — {finding['title']}")
    if findings_line:
        print(findings_line)
    if detail and verdict not in ("CLEAN", "FINDINGS"):
        print(f"detail: {detail}")
    return EXIT[verdict]


def parse_args(argv: list[str]) -> argparse.Namespace | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("pr", nargs="?")
    parser.add_argument("--timeout", default="900")
    parser.add_argument("--grace", default="900")
    parser.add_argument("--interval", default="30")
    parser.add_argument("--bot", default=DEFAULT_BOT)
    parser.add_argument("--findings-file", default="")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        print(f"Unknown argument: {unknown[0]}", file=sys.stderr)
        return None
    if not args.pr or not args.pr.lstrip("#").isdigit():
        print("Usage: review_watch.py <pr-number> [--timeout SECONDS] [--bot LOGIN]",
              file=sys.stderr)
        return None
    args.pr = args.pr.lstrip("#")
    for name in ("timeout", "grace", "interval"):
        value = getattr(args, name)
        if not str(value).isdigit():
            print(f"--{name} needs a whole number of seconds, got: {value}",
                  file=sys.stderr)
            return None
        setattr(args, name, int(value))
    if not args.bot.strip():
        print("--bot needs a login", file=sys.stderr)
        return None
    return args


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    args = parse_args(argv)
    if args is None:
        return 4

    start = time.monotonic()
    deadline = start + args.timeout
    state: dict | None = None
    last_error = ""
    first = True
    while True:
        try:
            state = poll(args.pr, args.bot, args.grace)
            last_error = ""
        except ReadError as exc:
            last_error = str(exc)
            # A PR that cannot be read on the first poll is a wrong number or
            # a lost token, not a slow reviewer: say so now, not at the end.
            if first and isinstance(exc, PrUnreadableError):
                return report("ERROR", args, state, 0,
                              f"could not read PR #{args.pr}: {last_error}")
        first = False
        waited = int(time.monotonic() - start)
        if state and state["verdict"] and not last_error:
            return report(state["verdict"], args, state, waited, state["detail"])
        if time.monotonic() >= deadline:
            if last_error:
                return report("ERROR", args, state, waited,
                              f"the last read failed: {last_error}")
            return report("PENDING_TIMEOUT", args, state, waited,
                          (state or {}).get("detail") or "still waiting")
        time.sleep(max(0.0, min(args.interval, deadline - time.monotonic())))


if __name__ == "__main__":
    sys.exit(main())

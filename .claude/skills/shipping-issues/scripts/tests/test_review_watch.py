#!/usr/bin/env python3
"""Tests for review_watch.py. Stdlib-only (unittest).

Run: python3 -m unittest discover -s scripts/tests -p 'test_*.py'
     (from the shipping-issues skill directory)

The fixtures copy the shapes the Codex GitHub integration actually posted on
this repository's PRs #159, #160, #170 and #171 (read 2026-10-07): the
edited-in-place summary comment (`🔄 **Running** since ...`, then
`✅ **Completed** ...`), a COMMENTED review, its inline comments with a
priority badge, and the 👍 reaction a clean review leaves.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fakegh import FakeGh  # noqa: E402


SCRIPT = Path(__file__).resolve().parent.parent / "review_watch.py"

BOT = "chatgpt-codex-connector[bot]"
HEAD = "564ca82e3ae32d38ecb4eae6bb59e6d59cd69e3f"
FIXED = "ba9af56003b69ac1f5f5b7e537e068c5de528f19"
MARKER = "<!-- codex-pull-request-review-summary -->"

# --- argv prefixes the script drives `gh` with --------------------------------


def PR_VIEW(pr):
    return ("pr", "view", pr, "--json", "headRefOid,createdAt,isDraft,state")


def ISSUE_COMMENTS(pr):
    return ("api", "repos/{owner}/{repo}/issues/%s/comments" % pr)


def REVIEWS(pr):
    return ("api", "repos/{owner}/{repo}/pulls/%s/reviews" % pr)


def INLINE(pr):
    return ("api", "repos/{owner}/{repo}/pulls/%s/comments" % pr)


def REACTIONS(pr):
    return ("api", "repos/{owner}/{repo}/issues/%s/reactions" % pr)


def COMMITS(pr):
    return ("api", "repos/{owner}/{repo}/pulls/%s/commits" % pr)


REPO_VIEW = ("repo", "view")

# --- payloads -----------------------------------------------------------------


def opened(seconds_ago):
    stamp = datetime.fromtimestamp(time.time() - seconds_ago, tz=timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def pr_json(seconds_ago=60, *, draft=False, head=HEAD):
    return json.dumps({"headRefOid": head, "createdAt": opened(seconds_ago),
                       "isDraft": draft, "state": "OPEN"})


def lines(*items):
    """What `gh api ... --paginate -q '.[] | @json'` prints: one object a line."""
    return "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)


def user(login=BOT, kind="Bot"):
    return {"login": login, "type": kind}


def summary_body(status="✅ **Completed**", sha="`564ca82`", trigger="PR opened"):
    return (
        f"{MARKER}\n\n## Codex Review Summary\n\n"
        "This comment shows the latest Codex review activity on this pull request.\n\n"
        "| Review | Status | Commit | Review trigger |\n"
        "| --- | --- | --- | --- |\n"
        f"| 📝 **Code Review** | {status} <relative-time datetime=\"2026-10-07T19:27:19.028799Z\">"
        f"2026-10-07T19:27:19Z</relative-time> | {sha} | {trigger} |\n\n"
        "<details> <summary>About Codex in GitHub</summary>\n</details>"
    )


def summary(body=None, *, author=None, cid=6045199702):
    return {"id": cid, "user": author or user(), "body": body or summary_body(),
            "created_at": "2026-10-07T19:24:54Z", "updated_at": "2026-10-07T19:27:19Z"}


def review(rid=5444206399, commit=HEAD, author=None):
    return {"id": rid, "user": author or user(), "state": "COMMENTED",
            "commit_id": commit, "body": "\n### 💡 Codex Review\n\nHere are some "
            "automated review suggestions for this pull request.\n",
            "html_url": "https://github.com/o/r/pull/7#pullrequestreview-%d" % rid}


def inline(cid, title, *, priority="P1", path="AGENTS.md", line=206,
           review_id=5444206399, reply_to=None, author=None):
    body = (f"**<sub><sub>![{priority} Badge](https://img.shields.io/badge/{priority}"
            f"-orange?style=flat)</sub></sub>  {title}**\n\nWhy it matters, in full.\n\n"
            "Useful? React with 👍 / 👎.")
    return {"id": cid, "user": author or user(), "pull_request_review_id": review_id,
            "in_reply_to_id": reply_to, "path": path, "line": line,
            "original_line": line, "commit_id": FIXED, "original_commit_id": HEAD,
            "html_url": "https://github.com/o/r/pull/7#discussion_r%d" % cid,
            "body": body}


def reaction(content="+1", author=None):
    # The reactions API reports the Codex app's reaction with type "User"
    # (observed on PR #170): the `[bot]` login is what identifies it.
    return {"content": content, "user": author or user(kind="User")}


def run_script(args, responses, *, sequences=None, exits=None, read=None):
    """Run the script against a fake gh; returns (proc, calls, file text).

    `read` names a path relative to the fake's state dir to read back before
    the temp dir goes away (the default findings file lives there)."""
    with FakeGh(responses, sequences=sequences, exits=exits) as fake:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args, "--interval", "0"],
            env=fake.env, text=True, capture_output=True,
        )
        calls = list(fake.calls)
        text = None
        if read is not None:
            path = fake.state_dir / read
            text = path.read_text(encoding="utf-8") if path.exists() else None
    return proc, calls, text


def field(stdout, name):
    for line in stdout.splitlines():
        if line.startswith(name + ": "):
            return line[len(name) + 2:]
    return None


def completed(pr, *, extra=None, commits=(HEAD,)):
    """A PR whose opening review completed for HEAD; `extra` adds responses."""
    responses = {
        PR_VIEW(pr): pr_json(),
        ISSUE_COMMENTS(pr): lines(summary()),
        COMMITS(pr): "".join(sha + "\n" for sha in commits),
        REPO_VIEW: "o/r",
    }
    responses.update(extra or {})
    return responses


class UsageTest(unittest.TestCase):
    def test_missing_pr_is_a_usage_error_and_never_calls_gh(self):
        proc, calls, _ = run_script([], {})

        self.assertEqual(proc.returncode, 4)
        self.assertIn("Usage: review_watch.py <pr-number>", proc.stderr)
        self.assertEqual(calls, [])

    def test_help_flag_prints_own_usage_and_never_calls_gh(self):
        for flag in ("-h", "--help"):
            with self.subTest(flag=flag):
                proc, calls, _ = run_script([flag], {})

                self.assertEqual(proc.returncode, 0)
                self.assertIn("review_watch.py — Wait for a PR's automatic", proc.stdout)
                self.assertIn("Exit codes: 0 = CLEAN", proc.stdout)
                self.assertEqual(calls, [])

    def test_a_non_numeric_timeout_is_a_usage_error(self):
        proc, calls, _ = run_script(["7", "--timeout", "soon"], {})

        self.assertEqual(proc.returncode, 4)
        self.assertIn("--timeout needs a whole number", proc.stderr)
        self.assertEqual(calls, [])

    def test_an_unknown_argument_is_a_usage_error(self):
        proc, calls, _ = run_script(["7", "--request-review"], {})

        self.assertEqual(proc.returncode, 4)
        self.assertIn("Unknown argument: --request-review", proc.stderr)
        self.assertEqual(calls, [])


class VerdictTest(unittest.TestCase):
    def test_an_unreadable_pr_is_an_error_at_once(self):
        pr = "7"
        proc, calls, _ = run_script([pr, "--timeout", "600"], {PR_VIEW(pr): ""},
                                    exits={PR_VIEW(pr): 1})

        self.assertEqual(proc.returncode, 4)
        self.assertEqual(field(proc.stdout, "verdict"), "ERROR")
        self.assertIn("could not read PR #7", field(proc.stdout, "detail"))
        self.assertEqual(len(calls), 1)

    def test_summary_not_posted_yet_on_a_young_pr_is_pending(self):
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "0"], {PR_VIEW(pr): pr_json(60)})

        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertEqual(field(proc.stdout, "verdict"), "PENDING_TIMEOUT")
        self.assertEqual(field(proc.stdout, "review_status"), "none")
        self.assertEqual(field(proc.stdout, "findings"), "0")
        self.assertIn("not posted yet", field(proc.stdout, "detail"))

    def test_no_trace_of_the_bot_past_the_grace_is_no_review(self):
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "600"], {PR_VIEW(pr): pr_json(1000)})

        self.assertEqual(proc.returncode, 3, proc.stdout)
        self.assertEqual(field(proc.stdout, "verdict"), "NO_REVIEW")
        self.assertIn("grace 900s", field(proc.stdout, "detail"))

    def test_a_shorter_grace_is_honoured(self):
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "0", "--grace", "30"],
                                {PR_VIEW(pr): pr_json(60)})

        self.assertEqual(field(proc.stdout, "verdict"), "NO_REVIEW")

    def test_a_running_review_past_the_grace_is_pending_not_no_review(self):
        pr = "7"
        running = summary(summary_body(status="🔄 **Running** since", sha="`564ca82`"))
        proc, _, _ = run_script([pr, "--timeout", "0"], {
            PR_VIEW(pr): pr_json(1000),
            ISSUE_COMMENTS(pr): lines(running),
            REACTIONS(pr): lines(reaction("eyes")),
        })

        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertEqual(field(proc.stdout, "verdict"), "PENDING_TIMEOUT")
        self.assertEqual(field(proc.stdout, "review_status"), "Running")
        self.assertEqual(field(proc.stdout, "completed_at"), "none")
        self.assertIn("Running", field(proc.stdout, "detail"))

    def test_completed_with_findings_lists_each_and_writes_bodies_to_a_file(self):
        pr = "7"
        human = {"login": "tomada1114", "type": "User"}
        proc, calls, text = run_script([pr, "--timeout", "0"], completed(pr, extra={
            REVIEWS(pr): lines(review()),
            INLINE(pr): lines(
                inline(4208464001, "Second finding", priority="P2",
                       path="src/x.py", line=3),
                inline(4208464000, "Adapt remaining Codex workflows"),
                inline(4208464002, "a reply in the thread", reply_to=4208464000),
                inline(4208464003, "a person's comment", author=human),
            ),
        }), read="shipping-issues/o__r/review/7-findings.md")

        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(field(proc.stdout, "verdict"), "FINDINGS")
        self.assertEqual(field(proc.stdout, "reviewed_sha"), "564ca82")
        self.assertEqual(field(proc.stdout, "head_sha"), HEAD)
        self.assertEqual(field(proc.stdout, "trigger"), "PR opened")
        self.assertEqual(field(proc.stdout, "findings"), "2")
        self.assertIn("  - F1 [P1] AGENTS.md:206 id=4208464000 — "
                      "Adapt remaining Codex workflows\n", proc.stdout)
        self.assertIn("  - F2 [P2] src/x.py:3 id=4208464001 — Second finding\n",
                      proc.stdout)
        # Bodies go to the file, never into the caller's output.
        self.assertNotIn("Why it matters", proc.stdout)
        self.assertTrue(field(proc.stdout, "findings_file").endswith(
            "shipping-issues/o__r/review/7-findings.md"))
        self.assertIn("## F1 [P1] AGENTS.md:206 id=4208464000", text)
        self.assertIn("Why it matters, in full.", text)
        self.assertNotIn("a person's comment", text)
        self.assertNotIn("a reply in the thread", text)
        self.assertIsNone(field(proc.stdout, "detail"))

    def test_an_explicit_findings_file_is_used(self):
        pr = "7"
        with FakeGh(completed(pr, extra={
            REVIEWS(pr): lines(review()),
            INLINE(pr): lines(inline(1, "One")),
        })) as fake:
            target = fake.state_dir / "elsewhere" / "f.md"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), pr, "--timeout", "0", "--interval", "0",
                 "--findings-file", str(target)],
                env=fake.env, text=True, capture_output=True,
            )
            written = target.read_text(encoding="utf-8")

        self.assertEqual(field(proc.stdout, "findings_file"), str(target))
        self.assertIn("## F1 [P1] AGENTS.md:206 id=1", written)

    def test_a_review_without_inline_comments_is_still_a_finding(self):
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "0"], completed(pr, extra={
            REVIEWS(pr): lines(review(rid=99)),
        }))

        self.assertEqual(field(proc.stdout, "verdict"), "FINDINGS")
        self.assertIn("  - F1 [P?] - id=review-99 — ", proc.stdout)

    def test_completed_with_no_findings_and_the_thumbs_up_is_clean(self):
        pr = "7"
        proc, calls, _ = run_script([pr, "--timeout", "0"], completed(pr, extra={
            REACTIONS(pr): lines(reaction("+1")),
        }))

        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(field(proc.stdout, "verdict"), "CLEAN")
        self.assertEqual(field(proc.stdout, "findings"), "0")
        self.assertEqual(field(proc.stdout, "thumbs_up"), "yes")
        self.assertEqual(field(proc.stdout, "reviewed_is_head"), "yes")
        self.assertEqual(field(proc.stdout, "completed_at"), "2026-10-07T19:27:19.028799Z")
        self.assertIsNone(field(proc.stdout, "findings_file"))
        # The reviewed commit is the head: the PR's commit list is never read.
        self.assertNotIn(list(COMMITS(pr)), [c[:2] for c in calls])

    def test_completed_with_no_findings_is_clean_without_the_thumbs_up(self):
        # The 👍 corroborates; its absence alone is neither a wait nor a finding.
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "0"], completed(pr))

        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(field(proc.stdout, "verdict"), "CLEAN")
        self.assertEqual(field(proc.stdout, "thumbs_up"), "no")

    def test_a_thumbs_up_from_anyone_else_is_not_reported_as_the_bots(self):
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "0"], completed(pr, extra={
            REACTIONS(pr): lines(reaction("+1", author={"login": "tomada1114",
                                                        "type": "User"})),
        }))

        self.assertEqual(field(proc.stdout, "thumbs_up"), "no")

    def test_a_thumbs_up_without_a_completed_summary_is_not_clean(self):
        pr = "7"
        running = summary(summary_body(status="🔄 **Running** since", sha="`564ca82`"))
        proc, _, _ = run_script([pr, "--timeout", "0"], {
            PR_VIEW(pr): pr_json(),
            ISSUE_COMMENTS(pr): lines(running),
            REACTIONS(pr): lines(reaction("+1")),
        })

        self.assertEqual(field(proc.stdout, "verdict"), "PENDING_TIMEOUT")

    def test_waits_through_not_posted_and_running_to_completion(self):
        pr = "7"
        running = summary(summary_body(status="🔄 **Running** since", sha="`564ca82`"))
        proc, calls, _ = run_script([pr, "--timeout", "60"], completed(pr), sequences={
            ISSUE_COMMENTS(pr): ["", lines(running), lines(summary())],
            REACTIONS(pr): ["", lines(reaction("eyes")),
                            lines(reaction("eyes"), reaction("+1"))],
        })

        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(field(proc.stdout, "verdict"), "CLEAN")
        summary_reads = [c for c in calls if tuple(c[:2]) == ISSUE_COMMENTS(pr)]
        self.assertEqual(len(summary_reads), 3)

    def test_a_marker_quoted_by_a_person_is_not_the_review(self):
        pr = "7"
        impostor = summary(author={"login": "chatgpt-codex-connector", "type": "User"})
        proc, _, _ = run_script([pr, "--timeout", "0"], {
            PR_VIEW(pr): pr_json(1000),
            ISSUE_COMMENTS(pr): lines(impostor),
        })

        self.assertEqual(field(proc.stdout, "verdict"), "NO_REVIEW")

    def test_a_non_bracket_login_needs_the_bot_account_type(self):
        pr = "7"
        other = "review-app"
        proc, _, _ = run_script([pr, "--timeout", "0", "--bot", other], {
            PR_VIEW(pr): pr_json(1000),
            ISSUE_COMMENTS(pr): lines(summary(author={"login": other, "type": "User"})),
        })

        self.assertEqual(field(proc.stdout, "verdict"), "NO_REVIEW")

    def test_the_bot_login_can_be_overridden(self):
        pr = "7"
        other = "another-reviewer[bot]"
        proc, _, _ = run_script([pr, "--timeout", "0", "--bot", other], completed(pr, extra={
            ISSUE_COMMENTS(pr): lines(summary(author=user(other))),
            REACTIONS(pr): lines(reaction("+1", author=user(other, "User"))),
        }))

        self.assertEqual(field(proc.stdout, "verdict"), "CLEAN")
        self.assertEqual(field(proc.stdout, "bot"), other)

    def test_a_failed_review_is_an_error(self):
        pr = "7"
        failed = summary(summary_body(status="❌ **Failed**", sha="`564ca82`"))
        proc, _, _ = run_script([pr, "--timeout", "600"], {
            PR_VIEW(pr): pr_json(),
            ISSUE_COMMENTS(pr): lines(failed),
        })

        self.assertEqual(proc.returncode, 4, proc.stdout)
        self.assertEqual(field(proc.stdout, "verdict"), "ERROR")
        self.assertIn("'Failed'", field(proc.stdout, "detail"))

    def test_a_reviewed_commit_that_is_not_on_the_pr_is_an_error(self):
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "0"], completed(
            pr, commits=(FIXED,), extra={PR_VIEW(pr): pr_json(head=FIXED),
                                         REACTIONS(pr): lines(reaction("+1"))}))

        self.assertEqual(proc.returncode, 4, proc.stdout)
        self.assertEqual(field(proc.stdout, "verdict"), "ERROR")
        self.assertIn("564ca82 is not a commit of PR #7", field(proc.stdout, "detail"))

    def test_a_completed_summary_with_no_commit_is_an_error(self):
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "0"], completed(pr, extra={
            ISSUE_COMMENTS(pr): lines(summary(summary_body(sha="—"))),
        }))

        self.assertEqual(field(proc.stdout, "verdict"), "ERROR")
        self.assertIn("names no reviewed commit", field(proc.stdout, "detail"))

    def test_a_review_of_an_earlier_commit_still_counts_after_a_push(self):
        # Fixes were pushed after the opening review: the head moved on, the
        # reviewed commit is still on the PR, and no new review is expected.
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "0"], completed(
            pr, commits=(HEAD, FIXED), extra={
                PR_VIEW(pr): pr_json(head=FIXED),
                REVIEWS(pr): lines(review()),
                INLINE(pr): lines(inline(1, "Fixed already")),
            }))

        self.assertEqual(field(proc.stdout, "verdict"), "FINDINGS")
        self.assertEqual(field(proc.stdout, "reviewed_sha"), "564ca82")
        self.assertEqual(field(proc.stdout, "head_sha"), FIXED)
        self.assertEqual(field(proc.stdout, "reviewed_is_head"), "no")

    def test_a_draft_pr_is_an_error_because_it_is_never_reviewed(self):
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "600"], {PR_VIEW(pr): pr_json(draft=True)})

        self.assertEqual(proc.returncode, 4)
        self.assertIn("is a draft", field(proc.stdout, "detail"))

    def test_a_read_failure_when_the_wait_ends_is_an_error_not_a_verdict(self):
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "0"], {
            PR_VIEW(pr): pr_json(1000),
            ISSUE_COMMENTS(pr): "",
        }, exits={ISSUE_COMMENTS(pr): 1})

        self.assertEqual(proc.returncode, 4, proc.stdout)
        self.assertEqual(field(proc.stdout, "verdict"), "ERROR")

    def test_a_transient_read_failure_is_retried(self):
        pr = "7"
        proc, _, _ = run_script([pr, "--timeout", "60"], completed(pr, extra={
            REACTIONS(pr): lines(reaction("+1")),
        }), sequences={
            ISSUE_COMMENTS(pr): [("", 1), lines(summary())],
        })

        self.assertEqual(field(proc.stdout, "verdict"), "CLEAN")

    def test_it_only_reads_and_never_asks_for_a_review(self):
        pr = "7"
        _, calls, _ = run_script([pr, "--timeout", "0"], completed(pr, extra={
            REVIEWS(pr): lines(review()),
            INLINE(pr): lines(inline(1, "One")),
        }))

        self.assertTrue(calls)
        for call in calls:
            with self.subTest(call=call):
                if call[0] == "api":
                    self.assertTrue(call[1].startswith("repos/{owner}/{repo}/"))
                else:
                    self.assertIn(call[:2], (["pr", "view"], ["repo", "view"]))
                self.assertNotIn("-X", call)
                self.assertNotIn("--method", call)
                self.assertNotIn("-f", call)
                self.assertNotIn("--field", call)


class LaterReviewTest(unittest.TestCase):
    """The summary keeps ONE row, rewritten for the latest review: on PRs #154
    and #156 (read 2026-10-07) a `@codex review` comment left a single
    `Manual request` row. So the watch remembers the opening review it saw
    settle, and a later, unsolicited review cannot replace that verdict."""

    def _two_runs(self, second_comments, *, second_extra=None):
        """Run 1 sees the opening review complete; run 2 sees the row rewritten."""
        pr = "7"
        later = second_comments
        responses = completed(pr, commits=(HEAD, FIXED), extra=second_extra or {})
        sequences = {
            ISSUE_COMMENTS(pr): [lines(summary()), later],
            PR_VIEW(pr): [pr_json(), pr_json(head=FIXED)],
        }
        with FakeGh(responses, sequences=sequences) as fake:
            argv = [sys.executable, str(SCRIPT), pr, "--timeout", "0", "--interval", "0"]
            first = subprocess.run(argv, env=fake.env, text=True, capture_output=True)
            second = subprocess.run(argv, env=fake.env, text=True, capture_output=True)
        return first, second

    def test_a_later_running_review_keeps_the_settled_opening_verdict(self):
        later = lines(summary(summary_body(status="🔄 **Running** since",
                                           sha=f"`{FIXED[:7]}`", trigger="Manual request")))
        first, second = self._two_runs(later)

        self.assertEqual(field(first.stdout, "verdict"), "CLEAN", first.stdout)
        self.assertEqual(second.returncode, 0, second.stdout)
        self.assertEqual(field(second.stdout, "verdict"), "CLEAN")
        self.assertEqual(field(second.stdout, "trigger"), "PR opened")
        self.assertEqual(field(second.stdout, "reviewed_sha"), "564ca82")
        self.assertEqual(field(second.stdout, "later_review"), "Running (Manual request)")

    def test_findings_a_later_review_already_posted_are_still_collected(self):
        pr = "7"
        later = lines(summary(summary_body(status="🔄 **Running** since",
                                           sha=f"`{FIXED[:7]}`", trigger="Manual request")))
        first, second = self._two_runs(later, second_extra={
            REVIEWS(pr): lines(review(rid=77, commit=FIXED)),
            INLINE(pr): lines(inline(9, "Found by the later review", review_id=77)),
        })

        # Run 1 already saw these findings (the fake answers both runs alike);
        # what matters is that run 2 still reports them under the opening verdict.
        self.assertEqual(field(second.stdout, "verdict"), "FINDINGS", second.stdout)
        self.assertEqual(field(second.stdout, "trigger"), "PR opened")
        self.assertIn("Found by the later review", second.stdout)

    def test_a_later_running_review_never_seen_settle_before_is_waited_for(self):
        # No memory of the opening review (another machine, a fresh state
        # dir): the only trusted completion left is the later review's own.
        pr = "7"
        later = summary(summary_body(status="🔄 **Running** since",
                                     sha=f"`{FIXED[:7]}`", trigger="Manual request"))
        proc, _, _ = run_script([pr, "--timeout", "0"], completed(pr, extra={
            ISSUE_COMMENTS(pr): lines(later),
        }))

        self.assertEqual(field(proc.stdout, "verdict"), "PENDING_TIMEOUT", proc.stdout)
        self.assertIn("Manual request", field(proc.stdout, "detail"))

    def test_a_completed_later_review_settles_when_the_opening_was_never_seen(self):
        pr = "7"
        later = summary(summary_body(sha=f"`{FIXED[:7]}`", trigger="Manual request"))
        proc, _, _ = run_script([pr, "--timeout", "0"], completed(
            pr, commits=(HEAD, FIXED), extra={
                PR_VIEW(pr): pr_json(head=FIXED),
                ISSUE_COMMENTS(pr): lines(later),
            }))

        self.assertEqual(field(proc.stdout, "verdict"), "CLEAN", proc.stdout)
        self.assertEqual(field(proc.stdout, "trigger"), "Manual request")


if __name__ == "__main__":
    unittest.main()

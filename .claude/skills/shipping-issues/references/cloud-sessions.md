# Cloud sessions

Read before a run in a Claude Code cloud session (`CLAUDE_CODE_REMOTE=true`). The
workflow and its scripts are unchanged there; what differs is how GitHub is reached and
what the VM keeps. Each item says what to expect and what to do instead of working
around it.

## Table of Contents

- [What the session starts with](#what-the-session-starts-with)
- [A push or GitHub call fails on every attempt](#a-push-or-github-call-fails-on-every-attempt)
- [Branch deletion is refused](#branch-deletion-is-refused)
- [A GraphQL call returns 403](#a-graphql-call-returns-403)
- [Hosts the network level blocks](#hosts-the-network-level-blocks)
- [Run state lives on the VM](#run-state-lives-on-the-vm)

## What the session starts with

The repository's `.claude/settings.json` SessionStart hook runs `just install` on start
and resume, so the environment and the git hooks are in place before step 1. A cloud
session reads no user-level or `.local` settings
([settings](https://code.claude.com/docs/en/settings), checked 2026-10-07): only what
the repository commits applies.

## A push or GitHub call fails on every attempt

All GitHub traffic goes through Anthropic's GitHub proxy with the credentials of the
owner's connected GitHub account
([cloud environments, GitHub proxy](https://code.claude.com/docs/en/cloud-environments#github-proxy),
checked 2026-10-07). A `git push` answered `remote: Internal Server Error` on every
retry was cured by the owner reconnecting GitHub at <https://claude.ai/connect-github>,
after which the same push went through (observed 2026-10-07).

So when a push, or every `gh` call, fails the same way after the usual retries: stop,
report which operation failed, and ask the owner to reconnect there. Never route around
it — no REST Git Data API commit, no `--no-verify` probe commit. Both are the denied
action re-spelled (AGENTS.md "Security and human approval"), and the host's permission
check refuses them anyway (observed 2026-10-07).

## Branch deletion is refused

The proxy rejects branch deletions and tag pushes
([GitHub proxy](https://code.claude.com/docs/en/cloud-environments#github-proxy),
checked 2026-10-07). The scripts already tolerate this: `land_pr.sh` reports `MERGED`
with a note when only the post-merge branch cleanup failed, and `cleanup_run.sh` prints
`SKIPPED` for a remote branch it could not delete. Neither is a failure of the run. With
the repository's "Automatically delete head branches" setting on, GitHub itself removes
the merged branch; otherwise name each remaining remote branch in step 10 for a human to
delete.

## A GraphQL call returns 403

The proxy serves only a pinned set of GraphQL operations and answers any other with a
403 that says `This GraphQL query is not enabled for this session` and names the REST
fallback ([GitHub proxy](https://code.claude.com/docs/en/cloud-environments#github-proxy),
checked 2026-10-07). Use the REST call the message names. A script whose verdict depends
on the refused call (for example `link_check.sh`, which reads `closingIssuesReferences`)
reports `ERROR`; treat that as [a non-verdict](recovery.md#no_checks-error-and-other-non-verdicts),
not as a missing link.

## Hosts the network level blocks

Under the default Trusted level, `api.osv.dev` answers 403 (observed 2026-10-07), so a
local vulnerability lookup for a new dependency cannot run. Say so in the review record
and let CI's OSV-Scanner and Dependency Review judge the pull request. **BACKGROUND:**
`managing-dependencies`.

## Run state lives on the VM

`<runstate>` is on the session VM, which is reclaimed after it sits idle for days
([claude-code-on-the-web](https://code.claude.com/docs/en/claude-code-on-the-web),
checked 2026-10-07). A run that resumes on a fresh VM starts with no `run.md`: rebuild
what it knows from GitHub (open PRs, their branches, labels) before writing anything.

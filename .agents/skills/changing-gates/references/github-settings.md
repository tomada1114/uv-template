# GitHub settings a new repository must enable

Read when a repository is created from this template, when a required check or a
security workflow changes, or when the repository becomes private. Every step here is a
human step on GitHub: an agent proposes it and never runs it.

## Main branch ruleset

`.github/rulesets/main.json` protects the default branch: no deletion, no force-push, a
pull request for every change (0 approvals), and the required status checks.
`just ruleset` creates it, or updates it by name, through `gh api`; it never deletes a
ruleset. Writing rulesets needs repository admin rights, so **`just ruleset` is a human
(admin) step** — an agent never runs it. Rerun it after editing `main.json`.

What makes a job fit to be a required check is in the skill's "CI workflows and required
checks".

## Security settings

Of the security workflows, only CodeQL (`codeql.yml`) uploads results, to code
scanning; OSV-Scanner (`osv-scanner.yml`) and gitleaks (`security-audit.yml`) just fail
the job. These are separate repository settings to turn on:

- Secret scanning, and its push protection
- Private vulnerability reporting (the route `SECURITY.md` gives)
- Dependabot alerts
- The dependency graph, which Dependency Review (`dependency-review.yml`) needs

Do not enable CodeQL "default setup": it rejects uploads from the advanced `codeql.yml`,
which fails the required "Analyze" checks.

## A private repository

On a private repository, CodeQL and Dependency Review need GitHub Code Security, and
secret scanning needs GitHub Secret Protection. Without them, delete `codeql.yml` and
`dependency-review.yml` rather than guarding them with an `if:` on visibility — but
first remove "Analyze (python)", "Analyze (actions)", and "Dependency Review" from
`.github/rulesets/main.json` (and from the context list in
`tests/test_apply_ruleset.py`) and have the owner re-run `just ruleset`, or every pull
request waits forever on them. `osv-scanner.yml`, `security-audit.yml`, and `ci.yml`'s
zizmor job run anywhere.

Private vulnerability reporting works only on public repositories, so a private
repository must replace the reporting route in `SECURITY.md` and the security contact
link in `.github/ISSUE_TEMPLATE/config.yml` with another contact.

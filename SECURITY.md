# Security Policy

## Reporting a Vulnerability

**Do NOT open a public issue for security vulnerabilities.**

Report it privately through GitHub's private vulnerability reporting:
open the repository's **Security** tab and choose **Report a vulnerability**,
or go straight to
[the new advisory form](https://github.com/your-username/uv-template/security/advisories/new).
Only the maintainers can see the report.

Include:

- Description of the vulnerability
- Steps to reproduce
- Affected commit or deployed version
- Suggested fix (if available)

## Response Timeline

This is a volunteer-maintained project, so every step below is best effort
rather than a guarantee: acknowledgment as soon as the report is seen,
assessment once acknowledged, and a fix on `main` (and in the deployed app) as soon as one is ready.
Serious, actively exploitable issues are prioritized over everything else.

## Supported Versions

Only the latest commit on `main` and the version deployed from it receive
security fixes; older commits and deployments do not.

## Responsible Disclosure

We follow a coordinated disclosure process. We ask that you:

1. Report the issue privately using the method above
2. Allow reasonable time for a fix before public disclosure
3. Avoid exploiting the vulnerability beyond what is necessary to demonstrate it

We will credit reporters in the fix's pull request or changelog entry unless they prefer to remain
anonymous.

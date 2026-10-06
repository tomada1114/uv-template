# The bootstrap

The detail behind `starting-an-app`'s rename step: what `scripts/bootstrap.py` takes,
what it refuses, what it changes and removes, and how it is proven. This page exists
only in the template: the bootstrap deletes it from both skill trees.

## Why a script, and why it runs once

Renaming an app by hand misses a site, and a careless global replace hits text that
merely explains the template. So the script replaces a fixed set of placeholders across
the tracked files, edits a short list of known sites (the contact slots, the copyright
line, the package metadata) that must each still be found exactly once, removes
everything marked as the template's own, and then deletes itself. A second run is
refused: `.template-origin` exists from the first one.

## Running it

From the root of a fresh clone, after `just install`:

```bash
uv run --locked python scripts/bootstrap.py todo-api \
  --author "Jane Doe" --github-user jdoe --github-repository jdoe/todo-api \
  --description "Todo API" --contact-url https://github.com/jdoe
```

| Flag | Required | Replaces | Rules |
|---|---|---|---|
| `name` (positional) | yes | `my-app` (distribution, console script, README text), `my_app` (the package, renamed `src/my_app` → `src/todo_api`), `MY_APP_` (the settings' environment prefix, `TODO_API_`) | lower-case letters and digits in words joined by single hyphens, starting with a letter, at most 40 characters |
| `--author` | yes | `Your Name` in `pyproject.toml` (TOML-quoted) and `LICENSE` | one line, at most 100 characters |
| `--description` | yes | the two "A short description …" sentences (`pyproject.toml`, README) | one line, at most 200 characters |
| `--github-user` | yes | the owner in `your-username/uv-template` | a GitHub user or organization name |
| `--github-repository` | no | the repository in `your-username/uv-template` | `NAME` or `OWNER/NAME`; the owner must equal `--github-user`; defaults to the slug |
| `--display-name` | no | `My App` (README's title, the API's OpenAPI title, the devcontainer) | one line, at most 60 characters; defaults to the slug |
| `--contact-url` | no | the contact sentences in `SECURITY.md` and `CODE_OF_CONDUCT.md` | a public `https://` URL without credentials, such as a profile page |
| `--keep-bootstrap` | no | — | keeps `TEMPLATE.md`, the script, and its test, untouched, for debugging; the kept test exercises the template, so `just verify` fails until they are deleted |

Without `--contact-url`, the contact sentences keep pointing at the repository itself:
`SECURITY.md`'s fallback route at the issue tracker (ask for a private contact, give no
detail), and `CODE_OF_CONDUCT.md`'s reports at the private vulnerability reporting form.
On a private repository that form does not exist, so pass `--contact-url` or follow
[private-repository.md](private-repository.md).

There is no `--email`, and argparse rejects one: an app cut from the template is
usually public, and its files are where people look for a contact, so no email address
is ever written. A value that looks like one is refused.

## What it refuses

Every refusal exits 1 with an `error:` line and writes nothing:

- not the root of a git work tree, or a work tree with any uncommitted or untracked
  change (`git status --porcelain --untracked-files=all` must be empty);
- `.template-origin` already present: the repository was bootstrapped;
- a reserved name: `app`, `src`, `test`, `tests`, `core`, `api`, `cli`, `adapters`,
  `settings`, `my-app`, `my_app`, any Python keyword, or any standard-library module
  (`sys.stdlib_module_names`) — checked in both the hyphenated and the underscored form;
- a value containing a placeholder (`my-app`, `my_app`, `my app`, `uv-template`,
  `your-username`, `your name`, any case), which the leftover scan would report;
- `src/my_app` missing or the destination package already present;
- a site that no longer has the shape the script expects: a contact sentence, the
  copyright line, the metadata lines, or a template-only block left open or closed
  twice. The template changed; fix the script's site list, not the file.

## What it does

1. Validates every value, then the repository's state.
2. Computes every file's new content in memory: removes each template-only block (a
   line holding only `<!-- template-only -->`, through the line holding only
   `<!-- /template-only -->`; in YAML, TOML, or a shell file the marker sits behind
   `#`), edits the known sites, and replaces the placeholders in one pass, so a new
   value is never rewritten again. `uv.lock`, the files it is about to delete, and
   secret-shaped paths are left alone.
3. Writes: the edited files; deletes `TEMPLATE.md`, `scripts/bootstrap.py`,
   `tests/test_bootstrap.py` (unless `--keep-bootstrap`), and this page in both skill
   trees; renames `src/my_app`; writes `.template-origin`. On top of the placeholders,
   `CHANGELOG.md` becomes an empty `[Unreleased]`, `LICENSE` gets the run's year and the
   author, and `pyproject.toml`'s `exclude-newer` moves to two weeks before the run.
   CI's `Template Bootstrap Smoke` job sits in a template-only block, so it goes too.
4. Runs `uv lock` (the lock still names the template's package), then
   `ruff check --fix` and `ruff format` (a longer module name can push imports past the
   line length). A failure here exits 1 after the write: run the failed command and
   the ones after it by hand.

`.template-origin` records the template's repository, the template commit, and the
tree. The commit is known only when the clone's history starts at the template's first
commit; GitHub's "Use this template" starts a new history, so there it reads `unknown`,
and the file says how to find the commit by its tree.

## How it is proven

- `tests/test_bootstrap.py` runs the script on a git clone of the working tree in a
  temporary directory, so an edit is tested before it is committed: every requirement
  above has a test, including that each refusal leaves the tree byte-identical.
- CI's `Template Bootstrap Smoke` job clones the commit under test, bootstraps it with
  the sample values above, fails on any placeholder left in the tracked or new files
  (`git grep` over everything but `.template-origin`, which names the template on
  purpose), checks that `tests/test_product_section.py` fails on the unfilled Product
  section, fills that section, and runs `just verify` there. It is not a required
  check, because an app no longer has it.

A change to the script, to a placeholder, or to a file it edits is proven by
`uv run --locked pytest tests/test_bootstrap.py` locally and that job on the pull
request.

## A placeholder survived

Search for every spelling at once:

```bash
git grep -n -i -E 'my-app|my_app|my app|uv-template|your-username|your name' -- . ':!.template-origin'
```

A hit is a spelling the placeholder list does not cover (a different case, a joined
form) or text that should have been template-only. Fix it by hand in the app, and fix
the template — the placeholder list or a template-only block — so the next app does
not inherit it.

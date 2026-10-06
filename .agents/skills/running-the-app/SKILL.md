---
name: running-the-app
description: >
  Covers observing the real my-app process when no test shows the behavior: running
  `uv run --locked my-app` commands against a scratch SQLite file, and starting
  `my-app serve` on a free port, capturing curl output as evidence, and stopping it
  before the turn ends, without starting, stopping, or reusing the developer's own
  server (`just dev`, port 8000). Use when asked to run the app, try a command or an
  endpoint by hand, check a change against a live server, or put command output in a
  pull request.
---

# Running the App

**Owns:** how an agent observes the running application — which evidence first, how to
start and stop a server of its own, and what the evidence looks like in a pull request.
**Does not own:** writing a route or its `TestClient` test (`building-api-routes`);
writing a command or its `CliRunner` test (`designing-clis`); the pull request's
mechanics (`create-pr`). The rule this skill carries out is AGENTS.md's "Quick
Reference", under "Long-running — human-run".

## Evidence, cheapest first

Stop at the first tier that shows what the change does.

1. **A test.** `TestClient` and `CliRunner` exercise the same code as a live process
   and the result outlives the turn. If a lasting assertion would show it, write one.
2. **The CLI, run for real,** against a scratch database (below). It shows the console
   script, the environment, and the exit codes exactly as a user meets them.
3. **A server of your own, then `curl`,** for what only a listening process shows: the
   served headers, the startup path through `my-app serve`, a request from outside the
   process.

## The developer's server is not yours

- `just dev` is the developer's: never start, stop, or restart it, and never bind its
  port, 8000, which is also `my-app serve`'s default — always pass `--port`.
- **Pick a free port** by asking the OS, and check that nothing listens on it before
  starting. A sibling worktree's server may hold any port.
- **Never reuse a server that is already answering,** even one that looks like this
  app: it may be the developer's, a sibling worktree's, or older code. Evidence comes
  only from a server you started from this checkout, in this turn.
- **Stop it by its pid, before the turn ends,** including when a step failed. Never by
  name (`pkill -f uvicorn`, `killall python`): that reaches the developer's server and
  every sibling's.
- **Loopback only.** `my-app serve` binds `127.0.0.1` by default; never pass
  `--host 0.0.0.0`.

## Choose the database explicitly

`MY_APP_DATABASE_URL` may be exported in the developer's shell, pointing at their real
data. Set it for every run: remove it (`env -u MY_APP_DATABASE_URL`) for the in-memory
store, or point it at a file in a directory from `mktemp -d`, outside the checkout. A
relative `sqlite:///todos.db` would create the file in the working directory.

## Running the CLI

Each command is its own process, so the in-memory store forgets between commands; use
a scratch file to see state carry over. Observed in this repository, 2026-10-06:

```console
$ export MY_APP_DATABASE_URL="sqlite:///$(mktemp -d)/todos.db"
$ uv run --locked my-app todo add "buy milk"; echo "exit=$?"
Added 1 [ ] buy milk
exit=0
$ uv run --locked my-app todo list; echo "exit=$?"
1 [ ] buy milk
exit=0
$ uv run --locked my-app todo complete 999; echo "exit=$?"
Error: To-do 999 not found
exit=1
```

## Running a server of your own

Run the whole life of the server as one foreground shell command — start, wait,
request, stop, confirm — so nothing outlives it. Do not use `set -e`: the `kill` must
run even when a `curl` fails.

```bash
port=$(uv run --locked python -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')
log=$(mktemp)
lsof -nP -iTCP:"$port" -sTCP:LISTEN && echo "port $port is taken; pick another"
env -u MY_APP_DATABASE_URL uv run --locked my-app serve --port "$port" >"$log" 2>&1 &
pid=$!
curl -fsS --retry 30 --retry-connrefused --retry-delay 1 -o /dev/null "http://127.0.0.1:$port/healthz" 2>/dev/null
curl -sS -i "http://127.0.0.1:$port/healthz"; echo
curl -sS -i -X POST "http://127.0.0.1:$port/todos" -H 'content-type: application/json' -d '{"title": "buy milk"}'; echo
kill "$pid"; wait "$pid"
lsof -nP -iTCP:"$port" -sTCP:LISTEN || echo "nothing listening on $port"
grep -E 'Uvicorn running|Finished server process' "$log"
```

- **Starting.** `&` applies to the whole `&&` chain before it, so keep the
  `port=` assignment on its own line, as above, or it is lost in a subshell.
- **A taken port.** If the `lsof` line reports the port taken, discard the run and
  start again with a new port: the requests would have reached someone else's server.
- **Waiting.** `curl --retry-connrefused` polls until the server answers, with no
  `sleep` loop.
- **Stopping.** `$!` is the pid of `uv`, not of the Python process that listens; `uv`
  passes the `SIGTERM` on and uvicorn shuts down cleanly (observed with this script,
  2026-10-06). The final `lsof` is the proof. If it still prints a listener, `kill` the
  pid it shows — the port was free when you started, so the listener is yours.
- **A host that runs long commands in the background** follows the same steps; the
  stop and the empty `lsof` still happen before the turn ends.

The output of that script, observed 2026-10-06 (the port and timestamps vary):

```console
HTTP/1.1 200 OK
date: Tue, 06 Oct 2026 21:20:07 GMT
server: uvicorn
content-length: 15
content-type: application/json

{"status":"ok"}
HTTP/1.1 201 Created
date: Tue, 06 Oct 2026 21:20:07 GMT
server: uvicorn
content-length: 88
content-type: application/json

{"id":1,"title":"buy milk","completed":false,"created_at":"2026-10-06T21:20:07.708499Z"}
nothing listening on 50101
INFO:     Uvicorn running on http://127.0.0.1:50101 (Press CTRL+C to quit)
INFO:     Finished server process [4596]
```

The in-memory store starts empty on every start; create what a request needs with a
`POST` first. Without the CLI there is no `my-app serve`: start the server with
`uv run --locked uvicorn my_app.api.app:create_app --factory --port "$port"`, the
command `just dev` runs, minus `--reload`. Without the API, only the CLI half applies.

## The evidence a pull request carries

Under the pull request's Test Plan, for each behavior observed rather than asserted:

- the exact command or request, as run;
- the lines of output that show the behavior — the status line, the body, the exit
  code, the stderr line — not the whole log;
- where it ran: `my-app serve` or the CLI, from this checkout, and the database
  (in-memory or a scratch file).

Redact before pasting: a home directory becomes `~/…`, a temporary path a placeholder,
and no credential or environment value appears.

## Before the turn ends

- [ ] Every port you used has no listener (`lsof -nP -iTCP:<port> -sTCP:LISTEN` prints
      nothing).
- [ ] The developer's server, if one was running, was never touched.
- [ ] `git status --porcelain` shows only the change: logs and databases live outside
      the checkout.

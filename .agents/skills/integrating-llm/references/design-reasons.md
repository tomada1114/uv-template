# Why the LLM layer is shaped this way

Read before adding a provider, swapping the HTTP client, moving `httpx` out of the `ai`
extra, or changing what an unconfigured layer answers. Each reason is the current design,
in the present tense; a pull request that changes the design rewrites the reason here
(`AGENTS.md`'s "Before changing the architecture"). The rules themselves are in the
skill; this page holds only why.

## A port, like any other outside service

A provider's SDK leaking into the business rules is the same mistake the core avoids
for HTTP frameworks (`designing-core-logic`'s
[references/design-reasons.md](../../designing-core-logic/references/design-reasons.md)).
So the model is one more port: `LlmPort` and its values in `core/llm.py` are plain
Python, and adapters implement it — `FakeLlm` for tests, `ClosedLlm` for an app with no
key, and `OpenRouterLlm`. The fake and the OpenRouter adapter pass one contract suite, so
a test on the fake says something about the real adapter.

## OpenRouter as the one provider

One key reaches many vendors' models, and the model is a setting (`MY_APP_LLM_MODEL`),
so trying another model is not a code change. A second provider is a second adapter
behind the same port ("Adding a provider" in the skill), not a branch inside this one.

## Raw `httpx`, not the `openai` SDK

`httpx` and everything it needs are already locked for FastAPI's `TestClient` (the `dev`
group), so the adapter adds no locked package. The SDK would add several for one POST,
and it brings its own retry and timeout layer, which would double the adapter's and break
the one-deadline rule below.

## An extra, not a group or a hard dependency

An extra is package metadata a wheel carries (`pip install 'my-app[ai]'`). A dependency
group never reaches a built package, so an installed app could not opt in; a hard
dependency would make every app carry `httpx` whether it calls a model or not.

## Closed by default, and 503 when closed

Without `OPENROUTER_API_KEY`, `build_llm` returns `ClosedLlm` and imports neither `httpx`
nor the adapter. The key alone opens the layer, so a billed endpoint is never open by
accident, and no sample route ships, so there is no billed endpoint to protect until an
app writes one. A route on the closed layer answers 503 rather than 500, because here a
500 means a bug and an unconfigured feature is not one.

## Bounded retries inside one deadline

`timeout` is one budget for the call, retries included, so retries never multiply what a
caller waits. Only the failures the skill lists as safe to repeat are retried, a small
fixed number of times, and a `Retry-After` longer than the cap ends the call rather than
holding it. The values — the 60 s default budget and the 8 s `Retry-After` cap — follow
the sibling nextjs-app-template's OpenRouter adapter. The exact rules and the known limit
(the deadline is checked between phases, not enforced as a hard cutoff) are in the skill's
"Retries and the deadline".

## No live call in the suite

A live call would bill, flake, and need a key in CI, and a skipped test is a weakened
gate. The OpenRouter adapter runs the contract suite over `httpx.MockTransport` instead,
and the owner checks a live key by hand ("Testing fake-first" in the skill).

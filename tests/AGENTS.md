# Testing Rules

## Structure and Organization

- File structure mirrors source: `tests/<layer>/test_<module>.py` for `src/my_app/<layer>/` (`core`, `adapters`, `api`, `cli`), `tests/test_<module>.py` for top-level modules (`settings`, `composition`)
- Shared fixtures go in `tests/conftest.py`; use the narrowest fixture scope possible
- Function names: `test_<what>_<scenario>_<expected_result>` (e.g. `test_parse_config_empty_string_raises_value_error`)
- Follow Arrange-Act-Assert; one logical behavior per test (several `assert` statements are fine if they verify that one behavior)

## What to Test

- Test *behavior and contracts*, not implementation details
- Test through each layer's public modules (`from my_app.core.services import TodoService`), never private helpers directly
- Drive the API with `fastapi.testclient.TestClient(create_app(settings))` and the CLI with `typer.testing.CliRunner`; build services through the composition root (the `make_container` fixture), never by hand-wiring adapters in an entry-point test
- Every repository adapter runs the one contract suite in `tests/adapters/test_repository_contract.py`; add a `pytest.param` there rather than a separate suite
- Always test the happy path AND the error path for every public function

## Edge Cases (always consider these)

- **Empty inputs**: empty string, empty list, empty dict, `None` where optional
- **Boundary values**: 0, 1, -1, max int, min int, `float("inf")`, `float("nan")`
- **Type boundaries**: very long strings, unicode/emoji, mixed encodings
- **Collection boundaries**: single element, duplicate elements, max expected size
- **Concurrent scenarios**: if the code is async, test cancellation and timeouts
- **State transitions**: initial state, after one operation, after repeated operations, after error recovery

## Error and Exception Testing

- Use `pytest.raises(XError, match=r"expected message")` — always verify the message pattern
- Test that cleanup runs even when exceptions occur (context managers, `finally`)
- Test error recovery: after an error, does the object remain in a consistent state?

## Parametrize and Data-Driven Tests

- Use `@pytest.mark.parametrize` for input/output variations; don't copy-paste test bodies
- Give related cases readable ids: `pytest.param(..., id="descriptive-name")`
- Consider `hypothesis` for functions with well-defined invariants (add it to the `dev` dependency group first)

## Fixtures

- Prefer factory fixtures over static ones: `def make_user(**overrides)` returns a customizable object
- Use `tmp_path` for filesystem work; never write into the repo tree
- Use `monkeypatch` for environment variables, not direct `os.environ` manipulation
- Fixtures that open resources must clean up with `yield` + teardown
- Scope fixtures appropriately: `function` for isolation, `session` only for truly expensive setup

## Mocking Strategy

- Mock at boundaries only: I/O, network, clock, external services — never the unit under test
- Prefer fakes (in-memory implementations) over mocks for repositories and stores: `InMemoryTodoRepository` is the core's fake, and the `fixed_clock` fixture fixes time
- Assert on behavior and outputs, not on how many times a mock was called — except when the call itself is the contract (retry/rate-limit behavior, a skipped step, proving no network call happened)
- Needing more than two mocks in one test usually means the code under test has too many dependencies

## Test Independence and Reliability

- No shared mutable state and no ordering dependency; each test must pass alone (`uv run pytest tests/test_foo.py::test_specific`)
- No `@pytest.mark.skip` or TODO tests on `main` — delete them or fix them
- No `time.sleep()` in tests; inject fakes or use `monkeypatch` for time
- Flaky tests must be fixed immediately, not ignored

## Coverage Philosophy

- Coverage is a *floor*, not a ceiling; keep the configured threshold and never lower it
- Branch coverage matters more than line coverage — test both sides of conditionals
- Missing coverage should prompt "is this code reachable?" — if not, delete it
- Don't write trivial tests to hit the number; cover edge cases and error paths instead

## Anti-Patterns

- Don't test getters and setters while missing business logic edge cases
- Don't write `assert True` or `assert result is not None` when a specific value can be checked
- Don't test that a dependency works (e.g. that `json.loads` parses JSON)
- Don't mock everything — tests against real collaborators catch real bugs

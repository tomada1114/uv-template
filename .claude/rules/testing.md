---
paths:
  - "tests/**/*.py"
---

# Testing Rules

## Structure and Organization

- File structure mirrors source: `tests/test_<module>.py`
- Shared fixtures go in `tests/conftest.py`; use the narrowest fixture scope possible
- Function names: `test_<what>_<scenario>_<expected_result>` (e.g. `test_parse_config_empty_string_raises_value_error`)
- Follow Arrange-Act-Assert; one logical behavior per test (several `assert` statements are fine if they verify that one behavior)

## What to Test

- Test *behavior and contracts*, not implementation details
- Test through the public API (`from my_package import ...`), never internal modules or private helpers directly
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
- Prefer fakes (in-memory implementations) over mocks for repositories and stores
- Assert on behavior and outputs, not on how many times a mock was called
- Needing more than two mocks in one test usually means the code under test has too many dependencies

## Test Independence and Reliability

- No shared mutable state and no ordering dependency; each test must pass alone (`uv run pytest tests/test_foo.py::test_specific`)
- No `@pytest.mark.skip` or TODO tests on `main` — delete them or fix them
- No `time.sleep()` in tests; inject fakes or use `monkeypatch` for time
- Flaky tests must be fixed immediately, not ignored

## Coverage Philosophy

- Coverage is a *floor*, not a *ceiling*; keep the configured threshold and never lower it
- Branch coverage matters more than line coverage — test both sides of conditionals
- Missing coverage should prompt "is this code reachable?" — if not, delete it
- Don't write trivial tests to hit the number; cover edge cases and error paths instead

## Anti-Patterns

- Don't test getters and setters while missing business logic edge cases
- Don't write `assert True` or `assert result is not None` when a specific value can be checked
- Don't test that a dependency works (e.g. that `json.loads` parses JSON)
- Don't mock everything — tests against real collaborators catch real bugs

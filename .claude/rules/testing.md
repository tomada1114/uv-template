---
paths:
  - "tests/**/*.py"
---

- Test files mirror source structure: `tests/test_<module>.py`
- Fixtures go in `tests/conftest.py`
- Coverage threshold: 80% (branch coverage enabled)
- Use `pytest.raises` for exception testing
- Use `@pytest.mark.parametrize` for multiple inputs
- Avoid excessive mocking of internal modules — test real behavior
- Test function names: `test_<what>_<expected_result>`
- Every file MUST start with `from __future__ import annotations`

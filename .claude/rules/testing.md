---
paths:
  - "tests/**/*.py"
---

# Testing Rules

- Test through the public API (`from my_package import ...`), not internal modules.
- Cover the error path of any function that raises: `pytest.raises(ExcType, match="...")`.
- Use `tmp_path` for filesystem work; never write into the repo tree.
- Never `time.sleep()` in tests — inject fakes or use monkeypatch.
- Prefer factory fixtures over shared mutable module-level data.
- Parametrize near-identical cases instead of copy-pasting tests.
- Keep the configured coverage threshold; do not lower it.

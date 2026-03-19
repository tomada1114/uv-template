---
paths:
  - "src/**/*.py"
  - "scripts/**/*.py"
---

- Every file MUST start with `from __future__ import annotations`
- All public functions and methods MUST have type annotations
- Use Google-style docstrings with Args/Returns/Raises sections
- Never use `Any` type without explicit justification in a comment
- Use `pathlib.Path` instead of `os.path` operations
- Never use `print()` in library code — use `logging` instead

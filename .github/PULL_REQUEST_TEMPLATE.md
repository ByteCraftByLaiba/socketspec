# Pull Request

## Summary

<!-- One sentence describing what this PR does. -->

## Related Issue

Fixes # <!-- issue number -->

## Type of Change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that changes existing behaviour)
- [ ] Refactor (no functional change)
- [ ] Documentation update
- [ ] CI / tooling change

## Changes

<!-- Bullet list of specific changes made. -->
-
-

## Testing

<!-- Describe the tests you added or ran. -->
- [ ] New unit tests added in `tests/unit/`
- [ ] Existing tests pass: `pytest tests/ -v`
- [ ] Coverage ≥ 90%: `pytest tests/ --cov=socketspec --cov-fail-under=90`

## Quality Checklist

- [ ] `mypy src/socketspec --strict` passes with zero errors
- [ ] `ruff check src/ tests/` passes
- [ ] Docstrings updated for any changed public API
- [ ] Copyright header present in every new `.py` file
- [ ] Absolute imports only (`from socketspec.X import Y`)
- [ ] No `print()` statements — using `logger` instead
- [ ] Changelog fragment added in `changes/<PR_NUMBER>.<type>.md`

## CLA

- [ ] I have signed the [Contributor License Agreement](../CLA.md)
      (the CLA bot will prompt me automatically if not)

## Screenshots / Output (if applicable)

<!-- For UI changes, paste a screenshot or terminal output. -->

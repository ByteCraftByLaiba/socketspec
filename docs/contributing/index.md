# Contributing to SocketSpec

Thank you for considering a contribution to SocketSpec!
This page is the entry point — from here you can find everything you need.

---

## Ways to Contribute

| Type | Where to start |
|---|---|
| Report a bug | [Bug report issue template](https://github.com/ByteCraftByLaiba/socketspec/issues/new/choose) |
| Request a feature | [Feature request template](https://github.com/ByteCraftByLaiba/socketspec/issues/new/choose) |
| Request a new adapter | [Adapter request template](https://github.com/ByteCraftByLaiba/socketspec/issues/new/choose) |
| Fix a bug | Find an issue labelled `good first issue` or `bug` |
| Write documentation | Find an issue labelled `documentation` |
| Write a new adapter | See [Writing a New Adapter](new-adapter.md) |

---

## Before You Start

All contributors must sign the [Contributor License Agreement (CLA)](../../CLA.md)
before their first PR is merged. The CLA bot will prompt you automatically when
you open a PR — just follow the comment instructions.

---

## Development Setup

```bash
git clone https://github.com/ByteCraftByLaiba/socketspec.git
cd socketspec

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install all dev dependencies
pip install -e ".[dev,fastapi]"

# Install pre-commit hooks
pre-commit install
```

---

## Running the Full Quality Check

This is the exact same check that CI runs. All three must pass before you open a PR:

```bash
# 1. Lint and format
ruff check src/ tests/
ruff format --check src/ tests/

# 2. Type check
mypy src/socketspec --strict

# 3. Tests with coverage
pytest tests/ --cov=socketspec --cov-fail-under=90 -v
```

---

## Coding Standards

Every file in `src/socketspec/` must follow [CODING_STANDARDS.md](../../.context/CODING_STANDARDS.md).
The key rules CI enforces:

- **Copyright header** — first thing in every `.py` file, no exceptions
- **`logger = logging.getLogger(__name__)`** — every module with logic
- **No `print()`** in library code — use the logger
- **No bare `except:`** — always catch a specific exception type
- **Absolute imports only** — `from socketspec.X import Y`, never relative imports
- **Google-style docstrings** — all public classes and methods

---

## Changelog Fragments

Every PR must include a changelog fragment:

1. Create `changes/<PR_NUMBER>.<type>.md`
2. `<type>` is one of: `feature`, `bugfix`, `deprecation`, `removal`, `misc`
3. Write one clear sentence describing the user-visible change

Example — `changes/42.bugfix.md`:
```
Fixed pong timeout not being tracked, causing ghost connections to accumulate on flaky networks.
```

Towncrier collects these into `CHANGELOG.md` at release time.

---

## Commit Message Style

```
type(scope): short description

Longer explanation if needed. Wrap at 72 chars.

Fixes #<issue_number>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`

---

## Code Review

- PRs are reviewed by the maintainer within 7 days
- Address all requested changes before re-requesting review
- Keep PRs focused — one feature or fix per PR
- Reference the related issue in the PR description

---

## Questions?

Open a [GitHub Discussion](https://github.com/ByteCraftByLaiba/socketspec/discussions)
or email [its.laiba.shahab@email.com](mailto:its.laiba.shahab@email.com).

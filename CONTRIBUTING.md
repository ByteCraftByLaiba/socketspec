# Contributing to SocketSpec

Thank you for your interest in contributing! SocketSpec is created and maintained by
[Laiba Shahab](https://github.com/ByteCraftByLaiba). All contributors must sign the
[Contributor License Agreement](CLA.md) before their first PR is merged — the CLA bot
will prompt you automatically when you open a PR.

---

## Quick Setup

```bash
git clone https://github.com/ByteCraftByLaiba/socketspec.git
cd socketspec
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,fastapi]"
pre-commit install
```

---

## Development Workflow

### Running Tests

```bash
pytest tests/ -v                         # full test suite
pytest tests/unit/ -v                    # unit tests only
pytest tests/ --cov=socketspec --cov-fail-under=90
```

### Type Checking

```bash
mypy src/socketspec --strict
```

### Linting

```bash
ruff check src/ tests/        # check
ruff check src/ tests/ --fix  # auto-fix safe issues
```

### Pre-commit (runs automatically on `git commit`)

```bash
pre-commit run --all-files   # manual run
```

---

## Project Structure

```
socketspec/
├── src/socketspec/       ← library source (absolute imports only)
│   ├── adapters/         ← framework adapters (FastAPI, etc.)
│   ├── backends/         ← storage backends (memory, redis)
│   ├── docs/             ← built-in docs UI and schema engine
│   └── security/         ← auth, rate limiting, origin validation
├── tests/
│   ├── unit/             ← isolated module tests
│   ├── integration/      ← full event flow tests
│   └── adapters/         ← adapter-specific tests
├── examples/             ← runnable example apps
└── docs/                 ← MkDocs documentation site
```

---

## Code Style

Every source file must follow [`.context/CODING_STANDARDS.md`](.context/CODING_STANDARDS.md).
Key rules enforced by CI:

- Apache 2.0 copyright header in every `.py` file
- `logger = logging.getLogger(__name__)` in every module with logic
- No `print()` in library code — use the logger
- No bare `except:` — always catch a specific exception
- Absolute imports only: `from socketspec.X import Y`, never `from .X import Y`
- Google-style docstrings on all public classes and methods
- `mypy --strict` must pass with zero errors

---

## Adding a New Adapter

See [docs/contributing/new-adapter.md](docs/contributing/new-adapter.md) for the
step-by-step guide. Adapters live in `src/socketspec/adapters/`.

---

## Changelog

All changes must be accompanied by a changelog fragment. Create a file at:

```
changes/<PR_NUMBER>.<type>.md
```

Where `<type>` is one of: `feature`, `bugfix`, `deprecation`, `removal`, `misc`.

Example — `changes/42.bugfix.md`:
```
Fixed pong timeout not being tracked after `__ping__` was sent.
```

Towncrier assembles these into `CHANGELOG.md` at release time.

---

## Pull Request Checklist

Before opening a PR, verify:

- [ ] Tests pass: `pytest tests/ -v`
- [ ] Type check passes: `mypy src/socketspec --strict`
- [ ] Linting passes: `ruff check src/ tests/`
- [ ] Changelog fragment added in `changes/`
- [ ] Docstrings updated for any changed public API
- [ ] CLA signed (bot will prompt automatically)

---

## Reporting Issues

- **Security vulnerabilities** — email [its.laiba.shahab@email.com](mailto:its.laiba.shahab@email.com) — **do not open a public issue**
- **Bugs** — open a [bug report](https://github.com/ByteCraftByLaiba/socketspec/issues/new/choose)
- **Feature requests** — open a [feature request](https://github.com/ByteCraftByLaiba/socketspec/issues/new/choose)
- **New adapter requests** — open an [adapter request](https://github.com/ByteCraftByLaiba/socketspec/issues/new/choose)

See [CLA.md](CLA.md) for the full Contributor License Agreement.

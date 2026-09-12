# Installation

SocketSpec is distributed as a pure-Python package on PyPI. Install it with pip, selecting the extras that match your deployment target.

---

## Requirements

- Python 3.10 or later
- A supported web framework (FastAPI is the primary adapter; others are planned)

---

## Install with FastAPI Support

Most users will want the FastAPI adapter and its dependencies (FastAPI, Uvicorn):

```bash
pip install socketspec[fastapi]
```

This installs SocketSpec along with `fastapi>=0.100` and `uvicorn>=0.29`.

---

## Install Core Only

If you are writing a custom adapter or using SocketSpec without a specific web framework:

```bash
pip install socketspec
```

Core dependencies are minimal: `pydantic>=2.0`, `anyio>=4.0`, and `PyJWT>=2.8`.

---

## Development Installation

For contributors and anyone running the test suite:

```bash
git clone https://github.com/ByteCraftByLaiba/socketspec.git
cd socketspec

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[dev,fastapi]"
pre-commit install
```

This installs all development tools: pytest, coverage, mypy, ruff, and pre-commit hooks.

---

## Verifying the Installation

```python
>>> import socketspec
>>> socketspec.__version__
'0.1.3'
```

---

## Optional Extras

| Extra | Installs | Use Case |
|---|---|---|
| `fastapi` | FastAPI, Uvicorn | Production deployment with FastAPI |
| `redis` | redis-py | Distributed pub/sub backend (planned) |
| `dev` | pytest, mypy, ruff, coverage | Running the test suite and linters |

---

## Next Steps

Once installed, proceed to the [Quickstart](quickstart.md) to build your first WebSocket API.

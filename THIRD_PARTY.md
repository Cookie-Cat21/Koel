# Third-party open-source dependencies

Chime installs packages from PyPI (or equivalent); we do **not** vendor
copies of upstream source trees into this repo.

| Package | License | Role |
|---|---|---|
| [httpx](https://github.com/encode/httpx) | BSD-3-Clause | HTTP client for cse.lk adapter |
| [tenacity](https://github.com/jd/tenacity) | Apache-2.0 | Retries / backoff on flaky upstream calls |
| [pydantic](https://github.com/pydantic/pydantic) | MIT | Internal schemas / validation |
| [structlog](https://github.com/hynek/structlog) | MIT / Apache-2.0 | Structured logging |
| [APScheduler](https://github.com/agronholm/apscheduler) | MIT | Market-hours poller schedule |
| [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | LGPL-3.0 | Telegram bot |
| [psycopg](https://github.com/psycopg/psycopg) (v3) | LGPL-3.0 | Postgres driver |

Dev extras (`pytest`, `ruff`, `mypy`, etc.) are listed in `pyproject.toml`
`[project.optional-dependencies]` and follow their own upstream licenses.

For usage notes and related bookmarks, see [docs/RESOURCES.md](docs/RESOURCES.md).

# Unofficial CSE (cse.lk) API Documentation

> Live-probed documentation of Colombo Stock Exchange public JSON/WebSocket endpoints.
> **Not affiliated with the CSE.** Data may change without notice.

[![Probe](https://github.com/Cookie-Cat21/Chime/actions/workflows/cse-api-docs-probe.yml/badge.svg)](../../actions)
[![Pages](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://cookie-cat21.github.io/Chime/cse-api-docs/)

## Why this exists

Community lists (e.g. [GH0STH4CKER](https://github.com/GH0STH4CKER/Colombo-Stock-Exchange-CSE-API-Documentation)) name endpoints but often skip request shapes, failure modes, and WebSocket. This project:

- Verifies each endpoint with an automated **probe harness**
- Stores **truncated samples** + last-verified dates
- Documents **STOMP** at `/api/ws`
- Ships **curl + Python** examples
- States **ethics** up front (rate limits, no auth abuse)

Born from research for [Chime](https://github.com/Cookie-Cat21/Chime) (Telegram CSE alerts). **This kit is separate** — extract to its own repo when ready (`EXTRACT.md`).

## Quick start

```bash
cd cse-api-docs
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Live probe (polite delays; writes samples/ + catalog/last_probe.json)
python3 scripts/probe.py

# Build static site into site/
python3 scripts/build_site.py

# Local preview
python3 -m http.server 8765 --directory site
# open http://127.0.0.1:8765/
```

## Layout

```
cse-api-docs/
  catalog/endpoints.yaml   # source of truth
  samples/                 # truncated live JSON
  scripts/probe.py         # verifier
  scripts/build_site.py    # static HTML docs
  docs/                    # markdown sources (ethics, websocket, …)
  examples/                # curl + python
  site/                    # generated (committed for Pages path)
```

## Ethics

Read [docs/ETHICS.md](docs/ETHICS.md). Short version: public endpoints only, polite rate limits, no competitor scrape, no credential stuffing, not financial advice.

## License

Documentation and harness: [MIT](LICENSE). CSE data remains subject to CSE terms; we claim no ownership of exchange data.

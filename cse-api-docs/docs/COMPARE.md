# Compared to GH0STH4CKER docs

| | [GH0STH4CKER](https://github.com/GH0STH4CKER/Colombo-Stock-Exchange-CSE-API-Documentation) | This project |
|---|---|---|
| Last meaningful update | ~2025-11 | Live probe timestamps in `catalog/last_probe.json` |
| Form | README table + one snippet | Catalog YAML + per-endpoint pages + samples |
| Request shapes / failures | Sparse | Documented per endpoint |
| `getAnnouncementByCompany` | Missing | Included |
| `daysTrade` | Missing | Included |
| `companyProfile` | Missing | Included |
| `news/web`, `events` | Missing | Included |
| WebSocket / STOMP | Not documented | Full topic + `/app/request-*` map |
| Automation | None | `scripts/probe.py` + CI |

We still credit that repo as an early public checklist that helped the community notice these endpoints exist.

# Log field glossary (ops)

Structured JSON logs via `chime.logging_setup` (structlog). Event name is the
first positional / `event` key. Never log `TELEGRAM_BOT_TOKEN`, raw DSNs with
passwords, or session cookie material.

Companion runbook: [docs/runbooks/PRODUCTION.md](../runbooks/PRODUCTION.md).

---

## `alert_latency_ms`

| | |
|---|---|
| **Where** | `chime/poller.py` after a successful claim→send for a price alert |
| **Level** | `INFO` |
| **Meaning** | Wall-clock milliseconds from start of `_claim_and_send` to successful delivery for that fire |
| **SLO** | Instrumented segment only — claim → Telegram send; target p95 &lt; 5s. **Not** CSE print → Telegram (that is poll-interval bounded) |

### Fields on the event

| Field | Type | Notes |
|---|---|---|
| `event` | string | Always `alert_latency_ms` |
| `rule_id` | int | Alert rule that fired |
| `latency_ms` | float | Rounded to 1 decimal |
| `event_key` | string | Idempotency / dedupe key for the fire |

### Dashboard / grep note

To chart claim→send latency, filter JSON lines where `event == "alert_latency_ms"`
and take `latency_ms`. There is no Prometheus `/metrics` export yet (WS-047 /
later epochs).

---

## Dead letter (`dead_letter` / related events)

An `alert_log` row is **dead-lettered** when delivery attempts are exhausted:
`dead_lettered = TRUE` in Postgres (`Storage.dead_letter`). Dead-lettered rows
are excluded from unsent claim batches.

| Constant | Value | Path |
|---|---|---|
| `MAX_SEND_ATTEMPTS` | 5 | Hard send failures |
| `MAX_DEFERRED_ATTEMPTS` | 30 | Telegram `RetryAfter` deferrals |

### Log events

| Event | Level | When |
|---|---|---|
| `alert_dead_lettered` | WARNING | Row marked dead-letter; `reason` is `failed` or `deferred` |
| `dead_letter_notify_sent` | INFO | One-shot Telegram notify to the user succeeded |
| `dead_letter_notify_failed` | WARNING / exception | Notify send failed (best-effort; no retry loop) |
| `dead_letter_notify_skipped` | WARNING | No `telegram_id` or symbol to notify |
| `alert_send_failed` | WARNING | Attempt incremented; not yet at ceiling |

### Common fields

| Field | Type | Notes |
|---|---|---|
| `alert_log_id` | int | `alert_log.id` |
| `rule_id` | int \| null | May be absent on some paths |
| `attempts` | int | Attempt count at decision time |
| `reason` | string | On `alert_dead_lettered`: `failed` \| `deferred` |
| `symbol` | string | On notify events |
| `send_result` | string | On non-exception notify failure |

DB column mirror: `alert_log.dead_lettered` (boolean). Grep logs with
`alert_dead_lettered` or `dead_letter_`; query DB with
`WHERE dead_lettered = TRUE`.

---

## `watched_missing`

| | |
|---|---|
| **Runtime** | `Poller.watched_missing: list[str]` — symbols on the watchlist absent from the latest trade-summary fetch |
| **Log event** | `watched_symbols_missing` (WARNING) when the list is non-empty after a price poll |
| **Health** | Exported on loopback `/health` as `watched_missing` (array of symbol strings) |

### Log fields (`watched_symbols_missing`)

| Field | Type | Notes |
|---|---|---|
| `count` | int | `len(missing)` |
| `symbols` | list[str] | Sorted missing CSE symbols |

### Health JSON (loopback only)

```json
{
  "status": "ok" | "degraded",
  "watched_missing": ["COMB.N0000", "..."],
  "price_poll_ok": false
}
```

Non-empty `watched_missing` sets `price_poll_ok` false for that tick path and
contributes to degraded health when the poller marks the tick unhealthy.
Empty watchlist clears the list (no warning). Health refresh also treats a
non-empty list as degraded on its own (HTTP **503**), even if other flags lag.

**Ops action:** confirm symbol spelling / listing status; CSE trade-summary
gaps are upstream — do not hammer the API. Non-loopback health binds omit
detail fields by design.

---

## Circuit breakers (`circuits` / `cse_circuit_open`)

Per-endpoint breakers live on `CSEClient` (`chime.circuit.CircuitBreaker`).
Open circuits short-call upstream and surface as poll-leg failures.

| | |
|---|---|
| **Log event** | `cse_circuit_open` (ERROR) when a call is rejected because the breaker is open |
| **Health** | Loopback `/health` field `circuits` — map of endpoint → snapshot |

### Snapshot fields (`circuits.<endpoint>`)

| Field | Type | Notes |
|---|---|---|
| `name` | string | Endpoint key (e.g. `tradeSummary`) |
| `state` | string | `closed` \| `open` \| `half_open` |
| `failures` | int | Consecutive failure count |
| `fail_max` | int | Trip threshold (`CIRCUIT_FAIL_MAX`) |
| `reset_timeout_seconds` | float | Open → half-open wait (`CIRCUIT_RESET_SECONDS`) |
| `half_open_trial` | bool | True while a half-open probe is in flight |

### Log fields (`cse_circuit_open`)

| Field | Type | Notes |
|---|---|---|
| `endpoint` | string | Breaker / path name |

Empty `circuits` `{}` means no endpoint has been exercised yet this process.
Dash `/health` proxies the same object when `HEALTH_URL` is set.

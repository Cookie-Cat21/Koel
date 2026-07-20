# Browse API — curl examples

Companion to [API_CONTRACT_V1.md](API_CONTRACT_V1.md) (§ Symbols / market data,
§ Sectors). Thin Postgres browse for `/market` — not a screener.

All three GETs require a valid **`koel_session`** cookie (ADR 001). CSRF is
**not** required on these safe GETs. Without a session → `401 unauthorized`
(or `503` if `DASH_SESSION_SECRET` is unset).

Set a base URL (local Next default shown):

```bash
export DASH_BASE_URL="${DASH_BASE_URL:-http://127.0.0.1:3000}"
```

## Mint a session cookie

Demo auth must be on (`DASH_DEMO_AUTH=1` + allowlisted `telegram_id` +
non-empty `DASH_SESSION_SECRET`):

```bash
# Writes Set-Cookie koel_session (+ koel_csrf) into the jar
curl -sS -c /tmp/koel.jar -D /tmp/koel-login.hdr \
  -X POST "${DASH_BASE_URL}/api/v1/auth/demo" \
  -H 'Content-Type: application/json' \
  -d '{"telegram_id":123456789}'
```

Reuse the jar with `-b /tmp/koel.jar` on the browse calls below. (Only
`koel_session` is needed for GETs; the CSRF cookie is unused here.)

Seed browse data first if the board is empty:

```bash
# From repo root — one poll cycle ignoring market hours
python -m koel tick --force
# Optional sectors board (empty items until this runs with the flag):
# SECTORS_INGEST=1 python -m koel tick --force
```

## `GET /api/v1/symbols`

Market browse list (latest `price_snapshots` via INNER JOIN). UI uses
`limit=100&sort=change_pct` (+ optional `q`).

```bash
# Default: limit=50, sort=change_pct
curl -sS -b /tmp/koel.jar \
  "${DASH_BASE_URL}/api/v1/symbols" | jq .

# Match /market: top movers by change_pct, capped list
curl -sS -b /tmp/koel.jar \
  "${DASH_BASE_URL}/api/v1/symbols?limit=100&sort=change_pct" | jq .

# Symbol/name substring search + alpha sort
curl -sS -b /tmp/koel.jar \
  --get "${DASH_BASE_URL}/api/v1/symbols" \
  --data-urlencode 'q=JKH' \
  --data-urlencode 'sort=symbol' \
  --data-urlencode 'limit=20' \
  --data-urlencode 'offset=0' | jq .
```

Query reminders: `limit` max `200`; `sort` is `change_pct` (default) or
`symbol`; `q` is optional case-insensitive substring.

**No session (expect 401):**

```bash
curl -sS -D - -o /tmp/koel-symbols.body \
  "${DASH_BASE_URL}/api/v1/symbols"
# Expect: HTTP … 401 … body contains "unauthorized"
```

## `GET /api/v1/market/movers`

Thin gainers/losers peek (same browse rows, sign-filtered). No `q` / sector /
volume filters.

```bash
# Gainers (default direction=up, limit=20)
curl -sS -b /tmp/koel.jar \
  "${DASH_BASE_URL}/api/v1/market/movers" | jq .

# /market strip: top 5 up / top 5 down
curl -sS -b /tmp/koel.jar \
  "${DASH_BASE_URL}/api/v1/market/movers?direction=up&limit=5" | jq .
curl -sS -b /tmp/koel.jar \
  "${DASH_BASE_URL}/api/v1/market/movers?direction=down&limit=5" | jq .
```

`direction` must be `up` or `down` (other values → `400` `validation_error`).
`limit` max `50`.

**No session (expect 401):**

```bash
curl -sS -D - -o /tmp/koel-movers.body \
  "${DASH_BASE_URL}/api/v1/market/movers"
# Expect: HTTP … 401 … body contains "unauthorized"
```

## `GET /api/v1/sectors`

Optional sector index board from Postgres `sectors` (poller
`SECTORS_INGEST=1`). Empty `items` when ingest has never run. No query params.

```bash
curl -sS -b /tmp/koel.jar \
  "${DASH_BASE_URL}/api/v1/sectors" | jq .
```

**No session (expect 401):**

```bash
curl -sS -D - -o /tmp/koel-sectors.body \
  "${DASH_BASE_URL}/api/v1/sectors"
# Expect: HTTP … 401 … body contains "unauthorized"
```

## Notes

- Contract shapes: [API_CONTRACT_V1.md](API_CONTRACT_V1.md).
- Unauthenticated browse gate is also asserted by
  `scripts/factory/dash_smoke.sh` (no cookie → 401/503).
- Mutating routes still need session **and** `X-CSRF-Token` — see
  `scripts/factory/test_csrf_contract.md`.

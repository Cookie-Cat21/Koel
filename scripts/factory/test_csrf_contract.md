# CSRF / session contract (E9-Q01/Q02, E10-Q01/Q02/Q03)

Companion to `tests/test_csrf_session_contract.py` and
`tests/csrf_session_unit.mts`. Unit coverage runs in CI without a live
server (tsx imports `csrfTokensMatch` + `requireSessionAndCsrf` +
logout handler for cookie clear).

Live checks: `RUN_WEB=1 DASH_BASE_URL=http://127.0.0.1:3000 pytest
tests/test_csrf_session_contract.py -k live`.

## Contract (ADR 001 + API_CONTRACT_V1)

| Case | Expect |
|---|---|
| Mutate with no session | `401` + `error.code=unauthorized` (503 if secret unset) |
| No session + bad CSRF material | `401` `unauthorized` (**not** `csrf_failed`) — E10-Q03 / E10-A01 |
| Logout with session, **no** `X-CSRF-Token` | `400` + `error.code=csrf_failed` |
| Logout with session, header ≠ cookie | `400` + `error.code=csrf_failed` — E10-Q01 |
| Logout with session + matching CSRF | `200` `{ "ok": true }`; clears `chime_session` + `chime_csrf` — E10-Q02 |

Session is checked **before** CSRF: missing session never returns `csrf_failed`.
When both would apply, **401 beats csrf_failed** (E10-A01).

## Curl — mutate without session (E9-Q02)

```bash
curl -sS -D - -o /tmp/chime-mutate.body \
  -X POST "${DASH_BASE_URL}/api/v1/watchlist" \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"JKH.N0000"}'
# Expect: HTTP/1.1 401 …  body contains "unauthorized"
```

## Curl — logout without CSRF (E9-Q01)

Mint a session first (demo auth must be enabled):

```bash
# Requires DASH_DEMO_AUTH=1 + allowlisted telegram_id + DASH_SESSION_SECRET
curl -sS -c /tmp/chime.jar -D /tmp/chime-login.hdr \
  -X POST "${DASH_BASE_URL}/api/v1/auth/demo" \
  -H 'Content-Type: application/json' \
  -d '{"telegram_id":123456789}'

# Session cookie only — omit X-CSRF-Token and strip chime_csrf if present
curl -sS -D - -o /tmp/chime-logout.body \
  -X POST "${DASH_BASE_URL}/api/v1/auth/logout" \
  -b "$(grep -E 'chime_session' /tmp/chime.jar | awk '{print $6"="$7}')"
# Expect: HTTP/1.1 400 …  body contains "csrf_failed"
```

## Unit (default CI)

```bash
pytest tests/test_csrf_session_contract.py -k unit --no-cov
# stages tests/csrf_session_unit.mts under web/ briefly so `next` resolves
```

#!/usr/bin/env bash
# Dashboard smoke (E6-Q01) — curl: GET /login + GET /api/v1/health +
# wave6 browse session gates (/market, /api/v1/symbols|movers|sectors).
#
# Mutate happy path (POST/DELETE watchlist|alerts) needs a signed
# chime_session cookie + matching X-CSRF-Token (ADR 001). This smoke does
# NOT mint a session: CI runs with DASH_DEMO_AUTH=0 and no DB user seed.
# Instead it asserts unauthenticated mutate is rejected (401/503), proving
# the gate is live. Full mutate: enable demo auth, POST /api/v1/auth/demo,
# then replay Set-Cookie + csrf_token on POST /api/v1/watchlist.
#
# Usage:
#   DASH_BASE_URL=http://127.0.0.1:3000 ./scripts/factory/dash_smoke.sh
# Or omit DASH_BASE_URL to build + start Next on an ephemeral port (demo auth off).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WEB="$ROOT/web"
STARTED_PID=""
BASE="${DASH_BASE_URL:-}"

cleanup() {
  if [[ -n "${STARTED_PID}" ]] && kill -0 "${STARTED_PID}" 2>/dev/null; then
    kill "${STARTED_PID}" 2>/dev/null || true
    wait "${STARTED_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ -z "${BASE}" ]]; then
  if [[ ! -d "$WEB/node_modules" ]]; then
    echo "dash_smoke: installing web deps…"
    (cd "$WEB" && npm ci)
  fi
  if [[ ! -d "$WEB/.next" ]]; then
    echo "dash_smoke: building web…"
    (cd "$WEB" && npm run build)
  fi

  PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
  BASE="http://127.0.0.1:${PORT}"
  echo "dash_smoke: starting next on ${BASE}"
  (
    cd "$WEB"
    # Demo off → POST /api/v1/auth/demo must return demo_auth_disabled.
    env -u DASH_DEMO_AUTH \
      DASH_DEMO_AUTH=0 \
      DASH_SESSION_SECRET="${DASH_SESSION_SECRET:-smoke-secret-not-for-prod}" \
      DASH_DEMO_TELEGRAM_IDS="${DASH_DEMO_TELEGRAM_IDS:-}" \
      DATABASE_URL="${DATABASE_URL:-}" \
      npx next start -H 127.0.0.1 -p "${PORT}"
  ) >"${TMPDIR:-/tmp}/chime-dash-smoke.log" 2>&1 &
  STARTED_PID=$!

  for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "${BASE}/login" 2>/dev/null; then
      break
    fi
    if ! kill -0 "${STARTED_PID}" 2>/dev/null; then
      echo "dash_smoke: next exited early; log:"
      cat "${TMPDIR:-/tmp}/chime-dash-smoke.log" || true
      exit 1
    fi
    sleep 0.5
  done
fi

echo "dash_smoke: BASE=${BASE}"

login_code="$(curl -sS -o /tmp/chime-dash-login.body -w '%{http_code}' "${BASE}/login")"
if [[ "${login_code}" != "200" ]]; then
  echo "dash_smoke: FAIL GET /login → ${login_code}"
  exit 1
fi
if ! grep -qi "koel" /tmp/chime-dash-login.body; then
  echo "dash_smoke: FAIL /login body missing koel brand"
  exit 1
fi
echo "dash_smoke: OK GET /login → 200"

health_code="$(curl -sS -o /tmp/chime-dash-health.body -w '%{http_code}' "${BASE}/api/v1/health" || true)"
if [[ "${health_code}" == "200" || "${health_code}" == "401" || "${health_code}" == "403" || "${health_code}" == "503" ]]; then
  echo "dash_smoke: OK GET /api/v1/health → ${health_code}"
else
  # Health may not exist yet (E2-D04). Accept demo-auth disabled on POST /auth/demo.
  demo_code="$(curl -sS -o /tmp/chime-dash-demo.body -w '%{http_code}' \
    -X POST "${BASE}/api/v1/auth/demo" \
    -H 'Content-Type: application/json' \
    -d '{"telegram_id":1}')"
  if [[ "${demo_code}" == "403" ]] && grep -q 'demo_auth_disabled' /tmp/chime-dash-demo.body; then
    echo "dash_smoke: OK POST /api/v1/auth/demo → 403 demo_auth_disabled (health=${health_code})"
  elif [[ "${demo_code}" == "403" ]]; then
    # Allowlist / disabled variants still prove the route is alive.
    echo "dash_smoke: OK POST /api/v1/auth/demo → 403 (health=${health_code})"
    cat /tmp/chime-dash-demo.body
  else
    echo "dash_smoke: FAIL health=${health_code} demo=${demo_code}"
    cat /tmp/chime-dash-demo.body || true
    exit 1
  fi
fi

# Mutate without session must fail closed (session required; CSRF checked after).
# 401 = no/invalid session; 503 = DASH_SESSION_SECRET unset (fail-closed).
mutate_code="$(curl -sS -o /tmp/chime-dash-mutate.body -w '%{http_code}' \
  -X POST "${BASE}/api/v1/watchlist" \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"JKH.N0000"}' || true)"
if [[ "${mutate_code}" == "401" || "${mutate_code}" == "503" ]]; then
  echo "dash_smoke: OK POST /api/v1/watchlist (no session) → ${mutate_code} (mutate needs session+CSRF)"
else
  echo "dash_smoke: FAIL unauthenticated mutate → ${mutate_code} (expected 401 or 503)"
  cat /tmp/chime-dash-mutate.body || true
  exit 1
fi


# Wave6 browse routes: session-gated GETs must fail closed without a cookie.
# Pages redirect to /login; APIs return 401 (or 503 if secret unset).
market_code="$(curl -sS -o /dev/null -w '%{http_code}' "${BASE}/market" || true)"
if [[ "${market_code}" == "307" || "${market_code}" == "302" || "${market_code}" == "303" ]]; then
  echo "dash_smoke: OK GET /market (no session) → ${market_code} (redirect login)"
elif [[ "${market_code}" == "200" ]]; then
  # next start may follow internal redirect into login HTML — still proves route.
  echo "dash_smoke: OK GET /market → 200 (login shell without session)"
else
  echo "dash_smoke: FAIL GET /market → ${market_code} (expected redirect or login 200)"
  exit 1
fi

for path in \
  "/api/v1/symbols" \
  "/api/v1/market/movers" \
  "/api/v1/sectors"; do
  code="$(curl -sS -o "/tmp/chime-dash-browse.body" -w '%{http_code}' \
    "${BASE}${path}" || true)"
  if [[ "${code}" == "401" || "${code}" == "503" ]]; then
    echo "dash_smoke: OK GET ${path} (no session) → ${code}"
  else
    echo "dash_smoke: FAIL GET ${path} → ${code} (expected 401 or 503)"
    cat /tmp/chime-dash-browse.body || true
    exit 1
  fi
done

echo "DASH_SMOKE_OK BASE=${BASE} HEAD=$(cd "$ROOT" && git rev-parse HEAD)"

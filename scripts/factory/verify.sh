#!/usr/bin/env bash
# Canonical factory verify — cite output + git rev-parse HEAD in pass reports.
set -euo pipefail
cd "$(dirname "$0")/../.."
echo "HEAD=$(git rev-parse HEAD)"
ruff check chime tests
mypy chime
if [[ -f web/package.json ]]; then
  if [[ -d web/node_modules ]]; then
    (cd web && npm run lint && npm run typecheck)
    echo "web lint/typecheck ok — dash smoke: scripts/factory/dash_smoke.sh"
  else
    echo "web/ present (no node_modules) — CI runs lint/typecheck/dash_smoke"
  fi
fi
# Unit path: clear DATABASE_URL so integration tests stay skipped (CI/factory parity).
DATABASE_URL= pytest -q --tb=line
# E10-O01: portfolio_sum smoke — non-fatal (Plan A nodes stub may be empty/missing)
if python3 scripts/factory/portfolio_sum.py; then
  echo "portfolio_sum smoke ok"
else
  echo "portfolio_sum smoke failed (non-fatal)"
fi
echo "VERIFY_OK HEAD=$(git rev-parse HEAD)"

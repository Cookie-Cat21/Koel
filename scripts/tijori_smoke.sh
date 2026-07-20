#!/usr/bin/env bash
# Tijori smoke — import koel.briefs + koel.scenarios, and migrate --help.
#
# Usage:
#   ./scripts/tijori_smoke.sh
#   PYTHON=python3.12 ./scripts/tijori_smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

echo "tijori_smoke: checking koel.briefs / koel.scenarios imports…"
"${PYTHON}" -c "
from koel.briefs import briefs_enabled
from koel.scenarios import scenarios_enabled
print('imports_ok', 'briefs', briefs_enabled(), 'scenarios', scenarios_enabled())
"

echo "tijori_smoke: checking python -m koel migrate --help…"
"${PYTHON}" -m koel migrate --help >/dev/null

echo "TIJORI_SMOKE_OK HEAD=$(git rev-parse HEAD)"

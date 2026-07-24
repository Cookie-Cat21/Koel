#!/usr/bin/env bash
# Daily Loop-0 shadow ops for E7/E8 accumulation.
# Research/ledger only — never writes forecast_points or Telegram.
#
# Requires ambient env:
#   DATABASE_URL or ML_DATABASE_URL
#   KOEL_SECTOR_MAP (optional; defaults /tmp/koel-sector-map.json if present)
#
# Usage:
#   bash scripts/ml_daily_shadow.sh                 # run once now (post-close)
#   bash scripts/ml_daily_shadow.sh --wait          # sleep until next weekday 14:40 SLT, run once
#   bash scripts/ml_daily_shadow.sh --loop 60       # wait+run, repeat for N trading days
#   bash scripts/ml_daily_shadow.sh --loop 60 --wait
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
export ML_DATABASE_URL="${ML_DATABASE_URL:-${DATABASE_URL:-}}"
if [ -z "${ML_DATABASE_URL}" ]; then
  echo "ML_DATABASE_URL or DATABASE_URL required" >&2
  exit 1
fi
export DATABASE_URL="${DATABASE_URL:-$ML_DATABASE_URL}"
if [ -z "${KOEL_SECTOR_MAP:-}" ] && [ -f /tmp/koel-sector-map.json ]; then
  export KOEL_SECTOR_MAP=/tmp/koel-sector-map.json
fi

WAIT=0
LOOP=1
while [ $# -gt 0 ]; do
  case "$1" in
    --wait) WAIT=1; shift ;;
    --loop)
      LOOP=${2:?--loop requires a positive integer}
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done
if ! [[ "$LOOP" =~ ^[0-9]+$ ]] || [ "$LOOP" -lt 1 ]; then
  echo "--loop must be a positive integer" >&2
  exit 2
fi

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

secs_until_next_close() {
  python3 - <<'PY'
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
now = datetime.now(ZoneInfo("Asia/Colombo"))
target = now.replace(hour=14, minute=40, second=0, microsecond=0)
if now >= target:
    target = target + timedelta(days=1)
while target.weekday() >= 5:
    target += timedelta(days=1)
print(max(0, int((target - now).total_seconds())))
PY
}

e7_status() {
  python3 - <<'PY' || true
import os, psycopg
url = os.environ.get("ML_DATABASE_URL") or os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit(0)
with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(DISTINCT issued_at)
            FROM forecast_outcomes
            WHERE model_id = 'shadow_policy_rank_de_persist_v1'
              AND gate = 'shadow_persist_book'
            """
        )
        sessions = cur.fetchone()[0]
        cur.execute(
            """
            SELECT COUNT(*) FILTER (WHERE scored), COUNT(*)
            FROM forecast_outcomes
            WHERE model_id = 'shadow_policy_rank_de_persist_v1'
              AND gate = 'shadow_persist_book'
            """
        )
        scored, tot = cur.fetchone()
print(f"E7_STATUS non_partial_sessions={sessions}/60 scored_legs={scored}/{tot}")
PY
}

run_once() {
  local SNAP=/tmp/koel-live-final-snapshot-split
  local LOG_DIR=/tmp/koel-daily-shadow
  local STAMP
  STAMP=$(date -u +%Y%m%dT%H%M%SZ)
  mkdir -p "$LOG_DIR"

  log "export hybrid split snapshot"
  rm -rf "$SNAP"
  nice -n 10 python3 -m koel.ml.snapshot export \
    --dataset hybrid --output "$SNAP" --price-adjustment split \
    2>&1 | tee "$LOG_DIR/export-$STAMP.log"

  log "live_shadow emit"
  nice -n 10 python3 -m koel.ml.live_shadow --snapshot "$SNAP" \
    2>&1 | tee "$LOG_DIR/shadow-$STAMP.log"

  log "path-backfill recent CSE bars (period=2, force)"
  nice -n 15 python3 -m koel path-backfill --force --period 2 --limit 0 --no-seed \
    2>&1 | tee "$LOG_DIR/pathbf-$STAMP.log" || true

  log "score shadow outcomes first"
  nice -n 10 python3 -m koel ml-score-outcomes --model-prefix shadow --limit 20000 \
    2>&1 | tee "$LOG_DIR/score-$STAMP.log" || true

  log "live_shadow_report"
  nice -n 10 python3 -m koel.ml.live_shadow_report \
    2>&1 | tee "$LOG_DIR/report-$STAMP.log" || true

  e7_status | tee -a "$LOG_DIR/e7-$STAMP.log"
  log "DONE day stamp=$STAMP"
}

for day in $(seq 1 "$LOOP"); do
  if [ "$WAIT" -eq 1 ] || [ "$day" -gt 1 ]; then
    SECS=$(secs_until_next_close)
    log "loop $day/$LOOP sleeping ${SECS}s until next 14:40 Asia/Colombo weekday"
    sleep "$SECS"
  fi
  log "loop $day/$LOOP starting"
  run_once
done

log "LOOP COMPLETE days=$LOOP"
echo EXIT:0

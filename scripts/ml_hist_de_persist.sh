#!/usr/bin/env bash
# Research-only point-in-time DE-persist historical replay.
# Writes shadow_policy_rank_de_persist_hist_v1 / shadow_hist_persist_book.
# Does NOT count toward E7 prospective sessions. Never forecast_points/Telegram.
#
# Usage:
#   bash scripts/ml_hist_de_persist.sh --snapshot /tmp/koel-hist-snapshot-split --days 20
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
export ML_DATABASE_URL="${ML_DATABASE_URL:-${DATABASE_URL:-}}"
if [ -z "${ML_DATABASE_URL}" ]; then
  echo "ML_DATABASE_URL or DATABASE_URL required" >&2
  exit 1
fi

SNAP=""
DAYS=20
while [ $# -gt 0 ]; do
  case "$1" in
    --snapshot) SNAP=${2:?}; shift 2 ;;
    --days) DAYS=${2:?}; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
if [ -z "$SNAP" ] || [ ! -d "$SNAP" ]; then
  echo "--snapshot DIR required" >&2
  exit 2
fi

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

mapfile -t DATES < <(python3 - <<PY
from pathlib import Path
from koel.ml.snapshot import load_bar_snapshot
loaded = load_bar_snapshot(Path("$SNAP"))
dates = sorted({
    bar.trade_date
    for bars in loaded.series.values()
    for bar in bars
    if bar.trade_date.isoformat() >= "2025-01-01"
})
# Leave the final session unscored-safe: need a next bar in DB; emit through
# second-to-last snapshot date.
usable = dates[:-1] if len(dates) > 1 else dates
for d in usable[-int("$DAYS"):]:
    print(d.isoformat())
PY
)

log "hist DE-persist replay days=${#DATES[@]} snapshot=$SNAP"
for d in "${DATES[@]}"; do
  log "emit as-of=$d"
  nice -n 10 python3 -m koel.ml.live_shadow \
    --snapshot "$SNAP" \
    --as-of "$d" \
    | tee -a /tmp/koel-hist-de-persist.log
done

log "scoring hist (+ all shadow) rows"
python3 -m koel ml-score-outcomes --model-prefix shadow --limit 50000 \
  | tee -a /tmp/koel-hist-de-persist.log

python3 - <<'PY'
import os, psycopg
url = os.environ.get("ML_DATABASE_URL") or os.environ.get("DATABASE_URL")
with psycopg.connect(url) as conn, conn.cursor() as cur:
    cur.execute(
        """
        SELECT COUNT(DISTINCT issued_at) AS sessions,
               COUNT(*) AS legs,
               COUNT(*) FILTER (WHERE scored) AS scored_legs,
               AVG(hit::int) FILTER (WHERE scored) AS hit_rate
        FROM forecast_outcomes
        WHERE model_id = 'shadow_policy_rank_de_persist_hist_v1'
          AND gate = 'shadow_hist_persist_book'
        """
    )
    row = cur.fetchone()
    print(
        f"HIST_DE_STATUS sessions={row[0]} legs={row[1]} "
        f"scored_legs={row[2]} hit_rate={row[3]}"
    )
    print("NOTE: hist sessions are NOT E7-eligible (prospective only).")
PY

log "DONE"
echo EXIT:0

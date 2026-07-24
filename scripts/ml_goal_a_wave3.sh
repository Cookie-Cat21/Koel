#!/bin/bash
# Goal A wave3 — material_median labels on fpv2+liq_v4 near-miss carriers.
# Waits for hist DE (and any cpu_exhaust) to finish.
set -euo pipefail
cd /workspace
export PYTHONUNBUFFERED=1
export KOEL_SECTOR_MAP=/tmp/koel-sector-map.json
SNAP=/tmp/koel-live-final-snapshot-split
log(){ echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "waiting for hist DE / cpu_exhaust to idle"
while pgrep -f 'ml_hist_de_persist|koel.ml.live_shadow|cpu_exhaust' >/dev/null; do
  sleep 60
done
log "starting material_median nest"

mkdir -p /tmp/cpu-exhaust-rel-matmed-fpv2-liqv4
nice -n 10 python3 -m koel.ml.cpu_exhaust \
  --snapshot "$SNAP" \
  --output /tmp/cpu-exhaust-rel-matmed-fpv2-liqv4 \
  --target relative --horizon 1 \
  --label-policy material_median \
  --evaluation-domain cse --max-flat-fraction 0.40 \
  --screen-top-k 3 --nested-folds 3 --nested-seeds 0,1,2 \
  --skip-hyper --feature-pack v2 --universe-filter liq_v4 \
  --models xgb_two_stage,xgb_lmt,hgb_lmt \
  2>&1 | tee /tmp/cpu-exhaust-rel-matmed-fpv2-liqv4.log

mkdir -p /tmp/cpu-sel-ultradense-matmed-fpv2-liqv4
for model in xgb_two_stage xgb_lmt hgb_lmt; do
  shopt -s nullglob
  files=(/tmp/cpu-exhaust-rel-matmed-fpv2-liqv4/nested/*-${model}.predictions.jsonl.gz)
  [ ${#files[@]} -eq 0 ] && continue
  nice -n 10 python3 -m koel.ml.selective_gates "${files[@]}" --model "$model" \
    --coverage-grid 0.001,0.002,0.003,0.005,0.008,0.01,0.015,0.02,0.03,0.05 \
    --output-dir /tmp/cpu-sel-ultradense-matmed-fpv2-liqv4 || true
done
mkdir -p /tmp/cpu-disagree-matmed-fpv2-liqv4
nice -n 10 python3 -m koel.ml.selective_disagreement \
  --nested-dir /tmp/cpu-exhaust-rel-matmed-fpv2-liqv4/nested \
  --models xgb_two_stage,xgb_lmt,hgb_lmt \
  --primary-model xgb_lmt \
  --coverage-grid 0.001,0.002,0.003,0.005,0.008,0.01,0.015,0.02,0.03,0.05 \
  --output-dir /tmp/cpu-disagree-matmed-fpv2-liqv4 || true

python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime, timezone
roots=[
 Path('/tmp/cpu-sel-ultradense-matmed-fpv2-liqv4'),
 Path('/tmp/cpu-disagree-matmed-fpv2-liqv4'),
]
lines=[f"# Goal A wave3 material_median harvest — {datetime.now(timezone.utc).isoformat()}", ""]
any_met=False
for root in roots:
  best=None
  for p in root.glob('*.json') if root.exists() else []:
    d=json.loads(p.read_text()); sm=d.get('summary') or {}
    tup=(1 if d.get('contract_met') else 0, float(sm.get('precision_lcb') or 0), float(sm.get('precision') or 0), int(sm.get('emits') or 0), p.name)
    if best is None or tup>best: best=tup
  if best is None:
    lines.append(f"- `{root.name}`: no reports")
  else:
    met,lcb,prec,em,name=best
    any_met=any_met or bool(met)
    lines.append(f"- `{root.name}` best `{name}` contract={bool(met)} prec={prec:.4f} LCB={lcb:.4f} emits={em}")
nest=Path('/tmp/cpu-exhaust-rel-matmed-fpv2-liqv4/summary.json')
if nest.exists():
  s=json.loads(nest.read_text())
  lines.append(f"- nest label_policy={s.get('label_policy')} nested_contract_met={s.get('nested_contract_met')}")
  lines.append(f"- nested_per_model rank_ic: { {k:v.get('rank_ic') for k,v in (s.get('nested_per_model') or {}).items()} }")
lines += ["", f"ANY_CONTRACT_MET={any_met}", ""]
Path('/tmp/goal-a-wave3-harvest.md').write_text("\n".join(lines)+"\n")
print("\n".join(lines))
PY
log "WAVE3 COMPLETE"
echo EXIT:0

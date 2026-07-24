#!/bin/bash
set -euo pipefail
cd /workspace
export PYTHONUNBUFFERED=1
export KOEL_SECTOR_MAP=/tmp/koel-sector-map.json
SNAP=/tmp/koel-live-final-snapshot-split
log(){ echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
log "5-fold material_median for emit mass / fold stability"
nice -n 10 python3 -m koel.ml.cpu_exhaust \
  --snapshot "$SNAP" --output /tmp/cpu-exhaust-rel-matmed-fpv2-liqv4-f5 \
  --target relative --horizon 1 --label-policy material_median \
  --evaluation-domain cse --max-flat-fraction 0.40 \
  --screen-top-k 3 --nested-folds 5 --nested-seeds 0,1,2 \
  --skip-hyper --feature-pack v2 --universe-filter liq_v4 \
  --models xgb_two_stage,xgb_lmt,hgb_lmt \
  2>&1 | tee /tmp/cpu-exhaust-rel-matmed-fpv2-liqv4-f5.log
mkdir -p /tmp/cpu-sel-matmed-f5 /tmp/cpu-metalabel-matmed-f5 /tmp/cpu-disagree-matmed-f5
NEST=/tmp/cpu-exhaust-rel-matmed-fpv2-liqv4-f5/nested
for model in xgb_two_stage xgb_lmt hgb_lmt; do
  shopt -s nullglob; files=("$NEST"/*-${model}.predictions.jsonl.gz)
  [ ${#files[@]} -eq 0 ] && continue
  nice -n 10 python3 -m koel.ml.selective_gates "${files[@]}" --model "$model" \
    --coverage-grid 0.001,0.002,0.003,0.005,0.008,0.01,0.015,0.02,0.03,0.05,0.08,0.1,0.15 \
    --output-dir /tmp/cpu-sel-matmed-f5 || true
  nice -n 10 python3 -m koel.ml.selective_metalabel "${files[@]}" --model "$model" \
    --snapshot "$SNAP" --output-dir /tmp/cpu-metalabel-matmed-f5 || true
done
nice -n 10 python3 -m koel.ml.selective_disagreement \
  --nested-dir "$NEST" --models xgb_two_stage,xgb_lmt,hgb_lmt \
  --primary-model xgb_two_stage \
  --coverage-grid 0.001,0.002,0.003,0.005,0.01,0.02,0.05,0.1 \
  --output-dir /tmp/cpu-disagree-matmed-f5 || true
python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime, timezone
roots=[Path('/tmp/cpu-sel-matmed-f5'),Path('/tmp/cpu-metalabel-matmed-f5'),Path('/tmp/cpu-disagree-matmed-f5')]
lines=[f"# Goal A wave4 matmed 5-fold — {datetime.now(timezone.utc).isoformat()}","",]
any_met=False
for root in roots:
  best=None
  for p in root.glob('*.json') if root.exists() else []:
    d=json.loads(p.read_text()); sm=d.get('summary') or {}
    tup=(1 if d.get('contract_met') else 0, float(sm.get('precision_lcb') or 0), float(sm.get('precision') or 0), int(sm.get('emits') or 0), p.name)
    if best is None or tup>best: best=tup
  if best is None: lines.append(f"- `{root.name}`: none")
  else:
    met,lcb,prec,em,name=best; any_met=any_met or bool(met)
    lines.append(f"- `{root.name}` `{name}` contract={bool(met)} prec={prec:.4f} LCB={lcb:.4f} emits={em}")
s=json.loads(Path('/tmp/cpu-exhaust-rel-matmed-fpv2-liqv4-f5/summary.json').read_text()) if Path('/tmp/cpu-exhaust-rel-matmed-fpv2-liqv4-f5/summary.json').exists() else {}
if s:
  lines.append(f"- nest RankIC: { {k:v.get('rank_ic') for k,v in (s.get('nested_per_model') or {}).items()} }")
lines+=["",f"ANY_CONTRACT_MET={any_met}",""]
Path('/tmp/goal-a-wave4-harvest.md').write_text("\n".join(lines)+"\n")
print("\n".join(lines))
if any_met:
  Path('/tmp/SUCCESS_CONTRACT_OFFLINE').write_text('1')
  print('SUCCESS_CONTRACT_OFFLINE_MET')
PY
log DONE; echo EXIT:0

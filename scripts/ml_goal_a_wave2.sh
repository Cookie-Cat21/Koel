#!/bin/bash
# Goal A wave 2 — skip-day labels + h3 nest + horizon agreement.
# Waits for koel-goal-a-continue to finish; never weakens SuccessContract.
set -euo pipefail
cd /workspace
export PYTHONUNBUFFERED=1
export KOEL_SECTOR_MAP=/tmp/koel-sector-map.json
SNAP=/tmp/koel-live-final-snapshot-split
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "waiting for koel-goal-a-continue / cpu_exhaust to idle"
while pgrep -f '/tmp/koel-goal-a-continue.sh|cpu_exhaust.*fpv2-liqv4-nearmiss|cpu_exhaust.*fpv2-liqv4-f5|cpu_exhaust.*fpv3-liqv4' >/dev/null; do
  sleep 30
done
log "prior queue idle — starting wave 2"

run_exhaust() {
  local out=$1
  shift
  mkdir -p "$out"
  log "START $out -- $*"
  nice -n 10 python3 -m koel.ml.cpu_exhaust \
    --snapshot "$SNAP" \
    --output "$out" \
    "$@" \
    2>&1 | tee "${out}.log"
  test -f "$out/summary.json"
  log "DONE nest $out"
}

dense_selective() {
  local nested=$1 out=$2
  shift 2
  mkdir -p "$out"
  local model
  for model in "$@"; do
    shopt -s nullglob
    local files=("$nested"/*-${model}.predictions.jsonl.gz)
    if [ ${#files[@]} -eq 0 ]; then
      continue
    fi
    log "dense selective model=$model n=${#files[@]}"
    python3 -m koel.ml.selective_gates "${files[@]}" --model "$model" \
      --coverage-grid 0.001,0.0015,0.002,0.0025,0.003,0.004,0.005,0.006,0.0075,0.008,0.01,0.0125,0.015,0.0175,0.02,0.025,0.03,0.035,0.04,0.05,0.06,0.075,0.1,0.125,0.15 \
      --output-dir "$out" || true
  done
}

# ---- 1) skip-day label nest on cost-material matrix ----
if [ ! -f /tmp/cpu-exhaust-rel-skip1-fpv2-liqv4/summary.json ]; then
  run_exhaust /tmp/cpu-exhaust-rel-skip1-fpv2-liqv4 \
    --target relative --horizon 1 --label-skip 1 \
    --evaluation-domain cse --max-flat-fraction 0.40 \
    --screen-top-k 3 --nested-folds 3 --nested-seeds 0,1,2 \
    --skip-hyper --feature-pack v2 --universe-filter liq_v4 \
    --models xgb_two_stage,xgb_lmt,hgb_lmt
else
  log "skip skip-day nest — exists"
fi
bash /tmp/postprocess_any_nested.sh \
  /tmp/cpu-exhaust-rel-skip1-fpv2-liqv4/nested skip1-fpv2-liqv4 \
  /tmp/cpu-post-skip1-fpv2-liqv4 2>&1 | tee /tmp/post-skip1-fpv2-liqv4.log || true
dense_selective /tmp/cpu-exhaust-rel-skip1-fpv2-liqv4/nested /tmp/cpu-sel-ultradense-skip1-fpv2-liqv4 \
  xgb_two_stage xgb_lmt hgb_lmt
mkdir -p /tmp/cpu-disagree-skip1-fpv2-liqv4
nice -n 10 python3 -m koel.ml.selective_disagreement \
  --nested-dir /tmp/cpu-exhaust-rel-skip1-fpv2-liqv4/nested \
  --models xgb_two_stage,xgb_lmt,hgb_lmt \
  --primary-model xgb_lmt \
  --coverage-grid 0.001,0.002,0.003,0.005,0.008,0.01,0.015,0.02,0.03,0.05 \
  --output-dir /tmp/cpu-disagree-skip1-fpv2-liqv4 \
  2>&1 | tee /tmp/disagree-skip1-fpv2-liqv4.log || true

# ---- 2) h3 nest for horizon agreement (same matrix) ----
if [ ! -f /tmp/cpu-exhaust-rel-h3-fpv2-liqv4/summary.json ]; then
  run_exhaust /tmp/cpu-exhaust-rel-h3-fpv2-liqv4 \
    --target relative --horizon 3 \
    --evaluation-domain cse --max-flat-fraction 0.40 \
    --screen-top-k 3 --nested-folds 3 --nested-seeds 0,1,2 \
    --skip-hyper --feature-pack v2 --universe-filter liq_v4 \
    --models xgb_two_stage,xgb_lmt,hgb_lmt
else
  log "skip h3 nest — exists"
fi
dense_selective /tmp/cpu-exhaust-rel-h3-fpv2-liqv4/nested /tmp/cpu-sel-ultradense-h3-fpv2-liqv4 \
  xgb_two_stage xgb_lmt hgb_lmt

# ---- 3) horizon agreement h1×h3 (prefer existing h1 nest if present) ----
H1_NEST=""
for cand in \
  /tmp/cpu-exhaust-rel-h1-fpv2-liqv4-nearmiss/nested \
  /tmp/cpu-exhaust-rel-h1-fpv2-liqv4/nested
do
  if ls "$cand"/*-xgb_two_stage.predictions.jsonl.gz >/dev/null 2>&1; then
    H1_NEST=$cand
    break
  fi
done
if [ -n "$H1_NEST" ] && [ -d /tmp/cpu-exhaust-rel-h3-fpv2-liqv4/nested ]; then
  mkdir -p /tmp/cpu-horizon-agree-fpv2-liqv4
  for model in xgb_two_stage xgb_lmt hgb_lmt; do
    if ls "$H1_NEST"/*-${model}.predictions.jsonl.gz >/dev/null 2>&1 \
      && ls /tmp/cpu-exhaust-rel-h3-fpv2-liqv4/nested/*-${model}.predictions.jsonl.gz >/dev/null 2>&1; then
      log "horizon agree model=$model primary=$H1_NEST"
      nice -n 10 python3 -m koel.ml.selective_horizon_agree \
        --primary-nested-dir "$H1_NEST" \
        --secondary-nested-dir /tmp/cpu-exhaust-rel-h3-fpv2-liqv4/nested \
        --model "$model" \
        --coverage-grid 0.001,0.002,0.003,0.005,0.008,0.01,0.015,0.02,0.03,0.05 \
        --output-dir /tmp/cpu-horizon-agree-fpv2-liqv4 \
        2>&1 | tee -a /tmp/horizon-agree-fpv2-liqv4.log || true
    fi
  done
else
  log "horizon agree skipped — missing nests"
fi

# ---- 4) rich meta-label on skip-day + prior fpv2+liq_v4 nests ----
mkdir -p /tmp/cpu-metalabel-rich
for nest_model in \
  "/tmp/cpu-exhaust-rel-skip1-fpv2-liqv4/nested:xgb_two_stage" \
  "/tmp/cpu-exhaust-rel-skip1-fpv2-liqv4/nested:xgb_lmt" \
  "/tmp/cpu-exhaust-rel-h1-fpv2-liqv4-nearmiss/nested:xgb_lmt" \
  "/tmp/cpu-exhaust-rel-h1-fpv2-liqv4/nested:xgb_two_stage"
do
  nested=${nest_model%%:*}
  model=${nest_model##*:}
  shopt -s nullglob
  files=("$nested"/*-${model}.predictions.jsonl.gz)
  if [ ${#files[@]} -eq 0 ]; then
    continue
  fi
  log "rich metalabel nest=$nested model=$model"
  nice -n 10 python3 -m koel.ml.selective_metalabel "${files[@]}" \
    --model "$model" \
    --snapshot "$SNAP" \
    --output-dir /tmp/cpu-metalabel-rich \
    2>&1 | tee -a /tmp/metalabel-rich.log || true
done

# ---- harvest ----
python3 - <<'PY'
import json
from pathlib import Path
from datetime import datetime, timezone

def best_sel(dirpath: Path):
    best=None
    for p in dirpath.glob('*.json') if dirpath.exists() else []:
        d=json.loads(p.read_text())
        sm=d.get('summary') or {}
        tup=(
            1 if d.get('contract_met') else 0,
            float(sm.get('precision_lcb') or 0),
            float(sm.get('precision') or 0),
            int(sm.get('emits') or 0),
            d.get('model') or p.stem,
            str(p),
        )
        if best is None or tup > best:
            best=tup
    return best

roots=[
    Path('/tmp/cpu-sel-ultradense-skip1-fpv2-liqv4'),
    Path('/tmp/cpu-disagree-skip1-fpv2-liqv4'),
    Path('/tmp/cpu-post-skip1-fpv2-liqv4/selective'),
    Path('/tmp/cpu-sel-ultradense-h3-fpv2-liqv4'),
    Path('/tmp/cpu-horizon-agree-fpv2-liqv4'),
    Path('/tmp/cpu-metalabel-rich'),
    Path('/tmp/goal-a-continue-harvest.md'),
]
lines=[f"# Goal A wave2 harvest — {datetime.now(timezone.utc).isoformat()}", ""]
any_contract=False
for root in roots:
    if root.suffix == '.md':
        if root.exists():
            lines.append(f"- prior harvest present: `{root}`")
        continue
    b=best_sel(root)
    if b is None:
        lines.append(f"- `{root.name}`: no reports")
        continue
    met,lcb,prec,em,model,path=b
    any_contract = any_contract or bool(met)
    lines.append(f"- `{root.name}` best `{model}` contract={bool(met)} prec={prec:.4f} LCB={lcb:.4f} emits={em}")
# nest RankIC
for nest in [
    Path('/tmp/cpu-exhaust-rel-skip1-fpv2-liqv4/summary.json'),
    Path('/tmp/cpu-exhaust-rel-h3-fpv2-liqv4/summary.json'),
]:
    if nest.exists():
        s=json.loads(nest.read_text())
        lines.append(f"- nest `{nest.parent.name}` nested_contract_met={s.get('nested_contract_met')} label_skip={s.get('label_skip')}")
lines += ["", f"ANY_CONTRACT_MET={any_contract}", ""]
Path('/tmp/goal-a-wave2-harvest.md').write_text("\n".join(lines)+"\n")
print("\n".join(lines))
print("SUCCESS_CONTRACT_OFFLINE_MET" if any_contract else "SUCCESS_CONTRACT_STILL_UNMET")
PY

log "WAVE2 COMPLETE"
echo EXIT:0

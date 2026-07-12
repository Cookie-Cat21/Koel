#!/usr/bin/env bash
# Unofficial cse.lk API cheat sheet — polite use only.
set -euo pipefail
H=(-H 'Origin: https://www.cse.lk' -H 'Referer: https://www.cse.lk/' -H 'Accept: application/json')

echo '=== marketStatus ==='
curl -sS -X POST 'https://www.cse.lk/api/marketStatus' -H 'Content-Type: application/json' "${H[@]}" -d '{}'
echo

echo '=== companyInfoSummery ==='
curl -sS -X POST 'https://www.cse.lk/api/companyInfoSummery' \
  -H 'Content-Type: application/x-www-form-urlencoded' "${H[@]}" -d 'symbol=JKH.N0000' | head -c 400
echo

echo '=== tradeSummary (count) ==='
curl -sS -X POST 'https://www.cse.lk/api/tradeSummary' -H 'Content-Type: application/json' "${H[@]}" -d '{}' \
  | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('reqTradeSummery',[])))"

echo '=== companyProfile ==='
curl -sS -X POST 'https://www.cse.lk/api/companyProfile' \
  -H 'Content-Type: application/x-www-form-urlencoded' "${H[@]}" -d 'symbol=JKH.N0000' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(sorted(d.keys()))"

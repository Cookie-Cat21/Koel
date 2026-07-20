#!/usr/bin/env bash
# Smoke public marketing routes (unsigned). Requires Next on BASE_URL.
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:3000}"

check() {
  local path="$1"
  shift
  local html
  html="$(curl -fsS "${BASE_URL}${path}")"
  local needle
  for needle in "$@"; do
    if ! grep -qF "$needle" <<<"$html"; then
      echo "FAIL ${path}: missing '${needle}'" >&2
      exit 1
    fi
  done
  echo "ok ${path}"
}

check "/" \
  "koel-atmosphere" \
  "CSE alerts on Telegram" \
  "The cherry — Telegram" \
  "Alerts fire on Telegram" \
  "How it works" \
  "What you can watch for" \
  "Activity signals" \
  "Ready when the market moves" \
  "Not financial advice"

check "/pricing" \
  "Pricing" \
  "Free" \
  "Coming later" \
  "koel-atmosphere"

check "/legal/privacy" \
  "Privacy" \
  "koel-atmosphere" \
  "publicly available CSE"

check "/legal/terms" \
  "Terms" \
  "not investment advice" \
  "koel-atmosphere"

echo "marketing_smoke: all routes ok"

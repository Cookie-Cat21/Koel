# Epoch 2 — Wave A report (partial: E2-O03)

**Branch:** `cursor/epoch2-agentic-loop-cb19`  
**Item:** E2-O03 — Factory verify script + loop_status in CI or make  
**Status:** DONE

## Change

- Wired `python scripts/factory/loop_status.py` into the CI **unit** job (`.github/workflows/ci.yml`).
- Step must exit 0 (board + scoreboard parse smoke).
- Left existing Ruff / Mypy / Pytest steps in place; `scripts/factory/verify.sh` remains the local canonical verify for pass-report citations.

## Verify proof

```
$ python3 scripts/factory/loop_status.py
=== Chime Agentic Factory Status ===
...
exit 0
```

HEAD recorded at commit time.

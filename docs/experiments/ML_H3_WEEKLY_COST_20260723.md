# Relative/h3 weekly DE cost find — 2026-07-23

Research only — not financial advice.

## Finding

On split-adjusted nested relative/**h3** scores, portfolio construction
`weekly_5_sessions_top_bottom_05` on `double_ensemble_native` yields
**+0.27% mean net@112bps** over 111 sessions (gross 1.03%, turnover 0.34).

This is a **different** operating slice than h1 `persistence_exit_10_top_bottom_05`
(+0.49% offline). It does **not** meet selective 90% SuccessContract.

## Wired Loop 0 policy (review packet)

- ID: `shadow_policy_rank_de_h3_weekly_v1`
- Target/horizon: relative / 3
- Model: `double_ensemble_native`
- Book: rebalance every 5 sessions, top/bottom 5%
- Status: **wired** into `live_shadow.py` as ledger-only Goal B evidence.
  `live_shadow` trains relative/h3 samples only on weekly rebalance sessions;
  non-rebalance sessions re-emit prior book sides with incremented ages. Do not
  replace existing abs or h1 DE-persist policies.

## Gates

- SuccessContract: unmet
- User surfaces: blocked
- Forecast surface: blocked (`forecast_outcomes` only; no `forecast_points`)

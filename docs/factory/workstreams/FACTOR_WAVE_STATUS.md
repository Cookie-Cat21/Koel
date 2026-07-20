# Factor Factory — wave status

**Authority:** [FACTOR_INDEX.md](FACTOR_INDEX.md) · Signal Board plan  
**Concurrency:** ≤8 preferred / 16 hard · no 100-agent swarms

## Waves landed

| Wave | Model | IDs closed |
|---|---|---|
| 1 | `path_v1` | F-001,002,003,011,021,031,032,041 |
| 2 | `path_v2` | F-004,012,022,042 |
| 3 | `path_v3` | F-051,061,071,081 |
| 4 | `path_v4` | F-052,082 (+ notices-backfill) |
| 5 | `path_v5` | F-062,072 (+ whitespace company resolve) |

## Catalog rollup (100 IDs)

| Status | Count |
|---|---:|
| DONE | 20 |
| OPEN | 70 |
| DEFER | 10 |
| **Total** | **100** |

## Next packing (optional only)

Prefer high-data / low-ToS OPEN IDs: F-005,006,008,010,013,025,035,043,057,064.  
Pack ≤8 OWNED_FILES-disjoint. STOP lane after 2 clean no-lift passes.

## Explicitly not next

- Spawn 100 agents
- Tier B macros (F-091…100) without ToS checklist — roadmap unlocked in `MACRO_EXPANSION_MASTER_PLAN.md`; still intake-gated before prod flags
- Promote forecast until walk-forward hit rate ≥ 0.55

# Advisory lock deadlock audit — poll vs brief claim (wave 10)

**Date:** 2026-07-12  
**Branch:** `cursor/tijori-cse-phase1-e44e`  
**Verdict:** **Not a real deadlock** — no code change required. Do not unify lock IDs.

## Locks

| Lock | ID | API | Scope | Where |
|---|---|---|---|---|
| Poll tick | `4_201_337` (`POLL_LOCK_ID`) | `pg_try_advisory_lock` / unlock | **Session**, non-blocking try | `Poller.run_once` via `Storage.try_advisory_lock` |
| Brief daily cap | `4_201_339` (`BRIEF_CAP_LOCK_ID`) | `pg_advisory_xact_lock` | **Transaction**, blocking | `Storage.claim_pending_briefs` when `max_briefs_per_day` is set |

## Why there is no wait-for cycle

1. **Different advisory keys** — Postgres advisory locks only conflict on the same key. Poll and brief IDs never block each other.
2. **Poll never waits on the poll lock** — `pg_try_advisory_lock` fails fast (`poll_lock_held` / skip). No edge of a deadlock cycle can be “waiting for poll advisory.”
3. **No nesting** — Brief drain is scheduled **after** poll unlock (`_schedule_brief_drain`). The sticky `_lock_conn` is used only for acquire/unlock; claim SQL always checks out a separate pool connection.
4. **Brief row locks are non-blocking** — claim uses `FOR UPDATE OF b SKIP LOCKED`, so concurrent poll upserts / promote cannot form a row-lock cycle with the cap serializer.
5. **Brief xact hold is short** — lock covers count + claim only; LLM / PDF / Telegram run after commit.

## Footgun (why this stays deferred, not “merge the IDs”)

If both paths used the **same** bigint under `max_size=2`:

1. Poll holds conn1 with a **session** lock for the whole tick.
2. Brief drain takes conn2 and **blocks** on `pg_advisory_xact_lock` (same key) until poll unlocks.
3. Poll needs another pool connection for tick SQL → waits forever on conn2.

That is a real pool + advisory deadlock — prevented today only by **distinct IDs**. Keep them apart.

## Residual (out of scope)

- Pool starvation under load is availability, not this cross-lock cycle (`max_size >= 2` guard already exists).
- Concurrent brief drainers serialize on `BRIEF_CAP_LOCK_ID` (wait, not deadlock).

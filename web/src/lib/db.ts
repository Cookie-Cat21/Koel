import { Pool, type PoolClient } from "pg";

import { toIso } from "@/lib/api/time";
import type { AlertType } from "@/lib/api/symbol";

const globalForPg = globalThis as typeof globalThis & {
  __chimePgPool?: Pool;
};

export function getPool(): Pool {
  const url = (process.env.DATABASE_URL ?? "").trim();
  if (!url) {
    throw new Error("DATABASE_URL is not set");
  }
  if (!globalForPg.__chimePgPool) {
    globalForPg.__chimePgPool = new Pool({
      connectionString: url,
      max: 5,
    });
  }
  return globalForPg.__chimePgPool;
}

/** ensure_user for allowlisted demo IDs only (caller must gate allowlist). */
export async function ensureUser(telegramId: number): Promise<number> {
  const pool = getPool();
  const result = await pool.query<{ id: string | number }>(
    `INSERT INTO users (telegram_id)
     VALUES ($1)
     ON CONFLICT (telegram_id) DO UPDATE SET telegram_id = EXCLUDED.telegram_id
     RETURNING id`,
    [telegramId],
  );
  const row = result.rows[0];
  if (!row) throw new Error("ensure_user returned no row");
  return Number(row.id);
}

export type StockRow = {
  symbol: string;
  name: string | null;
};

/** Lookup stock in Postgres only — never call cse.lk from web. */
export async function getStock(symbol: string): Promise<StockRow | null> {
  const pool = getPool();
  const result = await pool.query<StockRow>(
    `SELECT symbol, name FROM stocks WHERE symbol = $1`,
    [symbol],
  );
  return result.rows[0] ?? null;
}

/**
 * Add watchlist row (ON CONFLICT DO NOTHING).
 * Caller must ensure symbol exists in stocks (FK).
 * Returns true if a new row was inserted.
 */
export async function addWatch(
  userId: number,
  symbol: string,
): Promise<boolean> {
  const pool = getPool();
  const result = await pool.query(
    `INSERT INTO watchlist_items (user_id, symbol)
     VALUES ($1, $2)
     ON CONFLICT DO NOTHING
     RETURNING symbol`,
    [userId, symbol],
  );
  return result.rowCount !== null && result.rowCount > 0;
}

/**
 * Atomically remove watchlist row and deactivate rules for symbol.
 * Mirrors Storage.unwatch_symbol.
 */
export async function unwatchSymbol(
  userId: number,
  symbol: string,
): Promise<{ removed: boolean; deactivated_alerts: number }> {
  const pool = getPool();
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const del = await client.query(
      `DELETE FROM watchlist_items
       WHERE user_id = $1 AND symbol = $2
       RETURNING symbol`,
      [userId, symbol],
    );
    const deactivated = await client.query(
      `UPDATE alert_rules
       SET active = FALSE
       WHERE user_id = $1 AND symbol = $2 AND active
       RETURNING id`,
      [userId, symbol],
    );
    await client.query("COMMIT");
    return {
      removed: del.rowCount !== null && del.rowCount > 0,
      deactivated_alerts: deactivated.rowCount ?? 0,
    };
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}

export type AlertRuleRow = {
  id: number;
  symbol: string;
  type: string;
  threshold: number | null;
  active: boolean;
  armed: boolean;
  created_at: string | null;
};

function mapRule(row: {
  id: string | number;
  symbol: string;
  type: string;
  threshold: number | null;
  active: boolean;
  armed: boolean;
  created_at: Date | string;
}): AlertRuleRow {
  return {
    id: Number(row.id),
    symbol: row.symbol,
    type: row.type,
    threshold: row.threshold == null ? null : Number(row.threshold),
    active: Boolean(row.active),
    armed: Boolean(row.armed),
    created_at: toIso(row.created_at),
  };
}

async function fetchActiveRule(
  client: PoolClient,
  userId: number,
  symbol: string,
  alertType: AlertType,
  threshold: number | null,
): Promise<AlertRuleRow | null> {
  const result = await client.query<{
    id: string | number;
    symbol: string;
    type: string;
    threshold: number | null;
    active: boolean;
    armed: boolean;
    created_at: Date | string;
  }>(
    `SELECT id, symbol, type, threshold, active, armed, created_at
     FROM alert_rules
     WHERE user_id = $1 AND symbol = $2 AND type = $3
       AND COALESCE(threshold, -1) = COALESCE($4::double precision, -1)
       AND active
     ORDER BY id DESC
     LIMIT 1`,
    [userId, symbol, alertType, threshold],
  );
  const row = result.rows[0];
  return row ? mapRule(row) : null;
}

function isUniqueViolation(err: unknown): boolean {
  return (
    typeof err === "object" &&
    err !== null &&
    "code" in err &&
    (err as { code: unknown }).code === "23505"
  );
}

/**
 * Create alert rule mirroring Storage.create_alert_rule:
 * auto-watch, idempotent return-existing, armed=true on insert.
 * Stock must already exist (caller checks).
 */
export async function createAlertRule(
  userId: number,
  symbol: string,
  alertType: AlertType,
  threshold: number | null,
): Promise<{ rule: AlertRuleRow; created: boolean }> {
  const pool = getPool();
  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    await client.query(
      `INSERT INTO watchlist_items (user_id, symbol)
       VALUES ($1, $2)
       ON CONFLICT DO NOTHING`,
      [userId, symbol],
    );

    const existing = await fetchActiveRule(
      client,
      userId,
      symbol,
      alertType,
      threshold,
    );
    if (existing) {
      await client.query("COMMIT");
      return { rule: existing, created: false };
    }

    try {
      const inserted = await client.query<{
        id: string | number;
        symbol: string;
        type: string;
        threshold: number | null;
        active: boolean;
        armed: boolean;
        created_at: Date | string;
      }>(
        `INSERT INTO alert_rules (user_id, symbol, type, threshold, active, armed)
         VALUES ($1, $2, $3, $4, TRUE, TRUE)
         RETURNING id, symbol, type, threshold, active, armed, created_at`,
        [userId, symbol, alertType, threshold],
      );
      const row = inserted.rows[0];
      if (!row) throw new Error("create_alert_rule returned no row");
      await client.query("COMMIT");
      return { rule: mapRule(row), created: true };
    } catch (err) {
      if (!isUniqueViolation(err)) throw err;
      // Concurrent insert won — return survivor
      await client.query("ROLLBACK");
      await client.query("BEGIN");
      const raced = await fetchActiveRule(
        client,
        userId,
        symbol,
        alertType,
        threshold,
      );
      await client.query("COMMIT");
      if (raced) return { rule: raced, created: false };
      throw err;
    }
  } catch (err) {
    try {
      await client.query("ROLLBACK");
    } catch {
      /* ignore */
    }
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Soft-cancel alert: active=false. Mirrors Storage.deactivate_alert.
 * Returns true if an active owned rule was deactivated.
 */
export async function cancelAlert(
  userId: number,
  ruleId: number,
): Promise<boolean> {
  const pool = getPool();
  const result = await pool.query(
    `UPDATE alert_rules
     SET active = FALSE
     WHERE id = $1 AND user_id = $2 AND active
     RETURNING id`,
    [ruleId, userId],
  );
  return result.rowCount !== null && result.rowCount > 0;
}

/** True if rule id exists and belongs to user (active or not). */
export async function alertOwnedByUser(
  userId: number,
  ruleId: number,
): Promise<boolean> {
  const pool = getPool();
  const result = await pool.query(
    `SELECT 1 FROM alert_rules WHERE id = $1 AND user_id = $2`,
    [ruleId, userId],
  );
  return result.rowCount !== null && result.rowCount > 0;
}

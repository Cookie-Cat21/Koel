import { Pool, type PoolClient } from "pg";

import { sanitizeDisclosureCategory } from "@/lib/api/disclosure-safe";
import { toFiniteNumber } from "@/lib/api/market-browse";
import { cappedAlertThreshold } from "@/lib/api/finite-number";
import { toNonNegativeSafeInt, toSafePositiveInt } from "@/lib/api/safe-int";
import { toIso } from "@/lib/api/time";
import { isAlertType, normalizeSymbol, type AlertType } from "@/lib/api/symbol";

const globalForPg = globalThis as typeof globalThis & {
  __chimePgPool?: Pool;
};

export function getPool(): Pool {
  // Fail closed — non-string env mocks used to throw on .trim mid pool init
  // (parity getDashAuthConfig / resolveInternalOrigin typeof guards).
  const urlEnv = process.env.DATABASE_URL;
  const url = typeof urlEnv === "string" ? urlEnv.trim() : "";
  if (!url) {
    throw new Error("DATABASE_URL is not set");
  }
  if (!globalForPg.__chimePgPool) {
    // Neon / managed Postgres usually require TLS. ``sslmode=require`` in the
    // URL is enough for libpq clients; node-pg needs an explicit ssl flag when
    // the host looks like Neon (or sslmode is in the query string).
    const needsSsl =
      /[?&]sslmode=(require|verify-full|verify-ca)/i.test(url) ||
      /\.neon\.tech\b/i.test(url);
    globalForPg.__chimePgPool = new Pool({
      connectionString: url,
      max: 5,
      ...(needsSsl ? { ssl: { rejectUnauthorized: false } } : {}),
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
  // Digits-only SafeInteger — Number(oversized) used to precision-lose and
  // mint a session for the wrong user_id after JSON/Number round-trip.
  const id = toSafePositiveInt(row.id);
  if (id == null || !Number.isSafeInteger(id)) {
    throw new Error("ensure_user returned non-safe id");
  }
  return id;
}

/** Record a dash session row for device list / logout-all (A2). */
export async function recordDashSession(
  userId: number,
  sid: string,
  userAgent: string | null,
): Promise<void> {
  if (!Number.isSafeInteger(userId) || userId <= 0) {
    throw new Error("userId must be a positive SafeInteger");
  }
  if (typeof sid !== "string" || !sid || sid.length > 64) {
    throw new Error("sid must be a non-empty string ≤64");
  }
  const ua =
    typeof userAgent === "string" && userAgent
      ? userAgent.slice(0, 200)
      : null;
  const pool = getPool();
  await pool.query(
    `INSERT INTO dash_sessions (user_id, sid, user_agent)
     VALUES ($1, $2, $3)
     ON CONFLICT (sid) DO UPDATE
       SET last_seen_at = now(),
           revoked_at = NULL,
           user_agent = COALESCE(EXCLUDED.user_agent, dash_sessions.user_agent)`,
    [userId, sid, ua],
  );
}

/**
 * True when sid is known and revoked. Unknown sid (pre-migration cookies)
 * returns false so existing sessions keep working until re-login.
 */
export async function isDashSessionRevoked(sid: string): Promise<boolean> {
  if (typeof sid !== "string" || !sid || sid.length > 64) return true;
  const pool = getPool();
  const { rows } = await pool.query<{ revoked: boolean }>(
    `SELECT (revoked_at IS NOT NULL) AS revoked
       FROM dash_sessions
      WHERE sid = $1
      LIMIT 1`,
    [sid],
  );
  if (rows.length === 0) return false;
  return rows[0]?.revoked === true;
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
  category: string | null;
  active: boolean;
  armed: boolean;
  created_at: string | null;
  muted_until: string | null;
};

function mapRule(row: {
  id: string | number;
  symbol: string;
  type: string;
  threshold: number | null;
  category: string | null;
  active: boolean;
  armed: boolean;
  created_at: Date | string;
  muted_until?: Date | string | null;
}): AlertRuleRow | null {
  // Digits-only SafeInteger — Number(oversized) used to precision-lose and
  // alias the wrong rule on create/idempotent return.
  const id = toSafePositiveInt(row.id);
  if (id == null || !Number.isSafeInteger(id)) return null;
  if (!isAlertType(row.type)) return null;
  // Fail closed — only CSE SYMBOL_RE (no sanitize "?" placeholder).
  const symbol = normalizeSymbol(row.symbol);
  if (!symbol) return null;
  return {
    id,
    symbol,
    type: row.type,
    // Finite-only + abs magnitude cap — NaN/±Inf / ±absurd → null.
    threshold: cappedAlertThreshold(toFiniteNumber(row.threshold)),
    category: sanitizeDisclosureCategory(row.category),
    // Strict === true — Boolean("false")/1 must not mislabel rule state.
    active: row.active === true,
    armed: row.armed === true,
    created_at: toIso(row.created_at),
    muted_until: toIso(row.muted_until ?? null),
  };
}

async function fetchActiveRule(
  client: PoolClient,
  userId: number,
  symbol: string,
  alertType: AlertType,
  threshold: number | null,
  category: string | null,
): Promise<AlertRuleRow | null> {
  const result = await client.query<{
    id: string | number;
    symbol: string;
    type: string;
    threshold: number | null;
    category: string | null;
    active: boolean;
    armed: boolean;
    created_at: Date | string;
    muted_until: Date | string | null;
  }>(
    `SELECT id, symbol, type, threshold, category, active, armed, created_at,
            muted_until
     FROM alert_rules
     WHERE user_id = $1 AND symbol = $2 AND type = $3
       AND COALESCE(threshold, -1) = COALESCE($4::double precision, -1)
       AND COALESCE(category, '') = COALESCE($5, '')
       AND active
     ORDER BY id DESC
     LIMIT 1`,
    [userId, symbol, alertType, threshold, category],
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
 * ``category`` is for disclosure rules only (substring filter); ignored otherwise.
 */
export async function createAlertRule(
  userId: number,
  symbol: string,
  alertType: AlertType,
  threshold: number | null,
  category: string | null = null,
): Promise<{ rule: AlertRuleRow; created: boolean }> {
  const pool = getPool();
  const client = await pool.connect();
  // Defense in depth: sanitize even if caller forgot (POST already sanitizes).
  const cat =
    alertType === "disclosure" ? sanitizeDisclosureCategory(category) : null;
  // MARKET halt is seeded by migration 009; other types require a known stock.
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
      cat,
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
        category: string | null;
        active: boolean;
        armed: boolean;
        created_at: Date | string;
        muted_until: Date | string | null;
      }>(
        `INSERT INTO alert_rules (user_id, symbol, type, threshold, category, active, armed)
         VALUES ($1, $2, $3, $4, $5, TRUE, TRUE)
         RETURNING id, symbol, type, threshold, category, active, armed, created_at,
                   muted_until`,
        [userId, symbol, alertType, threshold, cat],
      );
      const row = inserted.rows[0];
      if (!row) throw new Error("create_alert_rule returned no row");
      const mapped = mapRule(row);
      if (!mapped) throw new Error("create_alert_rule returned non-safe rule");
      await client.query("COMMIT");
      return { rule: mapped, created: true };
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
        cat,
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

export async function activeAlertQuota(userId: number): Promise<{
  active_count: number;
  alert_quota_max: number;
}> {
  const pool = getPool();
  const result = await pool.query<{
    active_count: string | number;
    alert_quota_max: string | number;
  }>(
    `SELECT
       (SELECT COUNT(*)::int FROM alert_rules WHERE user_id = $1 AND active) AS active_count,
       alert_quota_max
     FROM users
     WHERE id = $1`,
    [userId],
  );
  const row = result.rows[0];
  if (!row) throw new Error("active_alert_quota returned no row");
  const active_count = toNonNegativeSafeInt(row.active_count, 0);
  const quota = toNonNegativeSafeInt(row.alert_quota_max, 100);
  return {
    active_count,
    alert_quota_max: quota,
  };
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

/**
 * Set or clear alert mute. Returns null when the rule is not owned.
 */
export async function muteAlert(
  userId: number,
  ruleId: number,
  mutedUntil: string | null,
): Promise<AlertRuleRow | null> {
  const pool = getPool();
  const result = await pool.query<{
    id: string | number;
    symbol: string;
    type: string;
    threshold: number | null;
    category: string | null;
    active: boolean;
    armed: boolean;
    created_at: Date | string;
    muted_until: Date | string | null;
  }>(
    `UPDATE alert_rules
     SET muted_until = $1
     WHERE id = $2 AND user_id = $3
     RETURNING id, symbol, type, threshold, category, active, armed, created_at,
               muted_until`,
    [mutedUntil, ruleId, userId],
  );
  const row = result.rows[0];
  return row ? mapRule(row) : null;
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

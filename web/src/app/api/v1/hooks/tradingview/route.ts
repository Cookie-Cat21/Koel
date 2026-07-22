import type { NextRequest } from "next/server";

import { readJsonBody } from "@/lib/api/read-json-body";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const MAX_MSG = 900;

function nfaSuffix(text: string): string {
  const nfa = "\n\nNot financial advice — research only.";
  const body = text.trim();
  if (body.toLowerCase().includes("not financial advice")) {
    return body.slice(0, MAX_MSG);
  }
  return (body + nfa).slice(0, MAX_MSG + nfa.length);
}

/**
 * POST /api/v1/hooks/tradingview?token=…
 * Inbound TradingView webhook → Telegram for the matching koel user.
 * Does NOT replace the CSE poller as price truth.
 */
export async function POST(request: NextRequest) {
  const url = new URL(request.url);
  const token = (url.searchParams.get("token") || "").trim();
  if (token.length < 16 || token.length > 128) {
    return jsonError(401, "unauthorized", "Invalid webhook token.");
  }

  const botToken = process.env.TELEGRAM_BOT_TOKEN?.trim();
  const dryRun =
    url.searchParams.get("dry_run") === "1" ||
    url.searchParams.get("dry_run") === "true";
  if (!botToken && !dryRun) {
    return jsonError(503, "degraded", "Telegram delivery not configured.");
  }

  let messageBody = "";
  const contentType = request.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const parsed = await readJsonBody(request);
    if (!parsed.ok) {
      return jsonError(400, "validation_error", "Invalid JSON body.");
    }
    if (typeof parsed.value === "string") {
      messageBody = parsed.value;
    } else if (parsed.value && typeof parsed.value === "object") {
      const obj = parsed.value as Record<string, unknown>;
      if (typeof obj.message === "string") messageBody = obj.message;
      else if (typeof obj.text === "string") messageBody = obj.text;
      else messageBody = JSON.stringify(parsed.value);
    }
  } else {
    try {
      messageBody = (await request.text()).slice(0, MAX_MSG);
    } catch {
      return jsonError(400, "validation_error", "Could not read body.");
    }
  }

  messageBody = messageBody.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "").trim();
  if (!messageBody) {
    return jsonError(400, "validation_error", "Empty alert message.");
  }

  try {
    const pool = getPool();
    const user = await pool.query<{ id: number; telegram_id: string | number }>(
      `SELECT id, telegram_id FROM users WHERE tv_webhook_token = $1 LIMIT 1`,
      [token],
    );
    const row = user.rows[0];
    if (!row) {
      return jsonError(401, "unauthorized", "Invalid webhook token.");
    }
    const chatId = Number(row.telegram_id);
    if (!Number.isSafeInteger(chatId) || chatId <= 0) {
      return jsonError(503, "degraded", "User has no Telegram id.");
    }

    const text = nfaSuffix(`koel · TradingView\n${messageBody}`);
    if (dryRun || !botToken) {
      return jsonOk({
        ok: true,
        delivered: false,
        dry_run: true,
        telegram_id: chatId,
        preview: text.slice(0, 240),
      });
    }
    const tg = await fetch(
      `https://api.telegram.org/bot${botToken}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text,
          disable_web_page_preview: true,
        }),
      },
    );
    if (!tg.ok) {
      const detail = await tg.text().catch(() => "");
      console.error("TV webhook Telegram send failed", tg.status, detail.slice(0, 200));
      return jsonError(502, "upstream_error", "Telegram send failed.");
    }
    return jsonOk({ ok: true, delivered: true });
  } catch (err) {
    console.error("POST /hooks/tradingview failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}

import type { NextRequest } from "next/server";

import { toIso } from "@/lib/api/time";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

const POLL_MS = 5_000;
const CLOSE_AFTER_MS = 60_000;

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });
}

/**
 * GET /api/v1/stream/snapshots — session-gated EventSource heartbeat.
 * Polls Postgres only; never calls CSE from the dashboard.
 */
export async function GET(request: NextRequest) {
  const gated = requireSession(request);
  if (!gated.ok) return gated.response;

  const encoder = new TextEncoder();
  const started = Date.now();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      controller.enqueue(encoder.encode(": connected\n\n"));
      while (
        Date.now() - started < CLOSE_AFTER_MS &&
        !request.signal.aborted
      ) {
        try {
          const result = await getPool().query<{ max_ts: Date | string | null }>(
            `SELECT MAX(ts) AS max_ts FROM price_snapshots`,
          );
          const payload = JSON.stringify({
            last_snapshot_at: toIso(result.rows[0]?.max_ts ?? null),
          });
          controller.enqueue(
            encoder.encode(`event: snapshot\ndata: ${payload}\n\n`),
          );
        } catch {
          controller.enqueue(encoder.encode(": db_unavailable\n\n"));
        }
        await sleep(POLL_MS, request.signal);
      }
      controller.enqueue(encoder.encode(": closing\n\n"));
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}

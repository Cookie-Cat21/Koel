import type { NextRequest } from "next/server";

import { queryTapePulse } from "@/lib/api/tape";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

/**
 * GET /api/v1/market/tape — foreign flow + public book pressure (Postgres).
 */
export async function GET(request: NextRequest) {
  const gated = await requireSession(request);
  if (!gated.ok) return gated.response;

  try {
    const tape = await queryTapePulse(getPool());
    return jsonOk({
      ...tape,
      disclaimer:
        "Tape pulse uses koel’s accrued CSE market summary and public order-book totals sample. Not licensed Level-2 depth. Not financial advice.",
    });
  } catch (err) {
    console.error("GET /market/tape failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}

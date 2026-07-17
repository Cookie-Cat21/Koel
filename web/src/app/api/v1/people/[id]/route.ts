import type { NextRequest } from "next/server";

import { queryPersonDossier } from "@/lib/api/person-dossier";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { jsonError, jsonOk } from "@/lib/auth/errors";
import { requireSession } from "@/lib/auth/guard";
import { getPool } from "@/lib/db";

export const runtime = "nodejs";

type Ctx = { params: Promise<{ id: string }> };

/** GET /api/v1/people/:id — person dossier (seats + co-director network). */
export async function GET(_request: NextRequest, ctx: Ctx) {
  const gated = await requireSession(_request);
  if (!gated.ok) return gated.response;

  const { id: raw } = await ctx.params;
  const id = toSafePositiveInt(raw);
  if (id == null) return jsonError(400, "bad_request", "Invalid person id.");

  try {
    const pool = getPool();
    const dossier = await queryPersonDossier(pool, id);
    if (!dossier) return jsonError(404, "not_found", "Person not found.");
    return jsonOk({ person: dossier });
  } catch (err) {
    console.error("GET /people/[id] failed", err);
    return jsonError(503, "degraded", "Database unavailable.");
  }
}

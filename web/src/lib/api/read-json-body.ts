/**
 * Bound JSON body reader for dash mutating routes.
 *
 * Demo login / watchlist / alerts bodies are tiny. Unbounded ``request.json()``
 * lets a client OOM the Node route with a multi-MB payload (including
 * chunked transfer without Content-Length).
 */

import {
  resolveBoundedBodyCap,
} from "@/lib/api/read-bounded-text";
import { toNonNegativeSafeInt } from "@/lib/api/safe-int";

/** Cap for CSRF-gated mutation JSON (alerts / watchlist / demo). */
export const MAX_JSON_BODY_BYTES = 8_192;

export type ReadJsonOk = { ok: true; value: unknown };
export type ReadJsonFail = { ok: false; reason: "too_large" | "invalid_json" };
export type ReadJsonResult = ReadJsonOk | ReadJsonFail;

/**
 * Read at most ``maxBytes`` from the request body and JSON.parse.
 * Prefers Content-Length early-reject; always bounds the streamed buffer
 * so chunked bodies cannot allocate past the cap.
 */
export async function readJsonBody(
  request: Request,
  maxBytes: number = MAX_JSON_BODY_BYTES,
): Promise<ReadJsonResult> {
  // Fail closed — Math.max(1, NaN)===NaN disables total>cap stream gate;
  // abs-cap via resolveBoundedBodyCap (parity response body reader).
  const cap = resolveBoundedBodyCap(maxBytes);
  const lenHeader = request.headers.get("content-length");
  if (lenHeader != null && lenHeader.trim()) {
    const claimed = toNonNegativeSafeInt(lenHeader.trim(), -1);
    if (claimed < 0 || claimed > cap) {
      return { ok: false, reason: "too_large" };
    }
  }

  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    const reader = request.body?.getReader();
    if (!reader) {
      // No body stream (empty / already consumed) — treat as invalid JSON.
      return { ok: false, reason: "invalid_json" };
    }
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!value || value.byteLength === 0) continue;
      total += value.byteLength;
      if (total > cap) {
        try {
          await reader.cancel();
        } catch {
          /* ignore */
        }
        return { ok: false, reason: "too_large" };
      }
      chunks.push(value);
    }
  } catch {
    return { ok: false, reason: "invalid_json" };
  }

  if (total === 0) {
    return { ok: false, reason: "invalid_json" };
  }

  const buf = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    buf.set(chunk, offset);
    offset += chunk.byteLength;
  }

  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(buf);
    return { ok: true, value: JSON.parse(text) as unknown };
  } catch {
    return { ok: false, reason: "invalid_json" };
  }
}

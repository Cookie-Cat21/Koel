/**
 * Bound Response body reads for dash fetch paths.
 *
 * Content-Length early-reject alone is insufficient: a missing or
 * understated CL still lets ``res.text()`` allocate the full stream before
 * any length check. Stream + cancel past ``maxBytes`` (parity with
 * ``readJsonBody`` for request bodies).
 */

import { toNonNegativeSafeInt } from "@/lib/api/safe-int";

export type BoundedTextOk = { ok: true; text: string };
export type BoundedTextFail = {
  ok: false;
  reason: "too_large" | "read_error";
};
export type BoundedTextResult = BoundedTextOk | BoundedTextFail;

/**
 * Absolute ceiling for bounded body readers (parity sanitize text cap).
 * Medium: integer ``maxBytes`` of ``Number.MAX_SAFE_INTEGER`` used to let a
 * misbuilt caller stream-allocate multi-PB responses before any product cap.
 * SSR / client mutate already use ≤1 MiB; this is the hard ceiling.
 */
export const MAX_BOUNDED_BODY_BYTES = 1_048_576;

/**
 * Fail-closed positive body cap — NaN/≤0 → 1; oversized → absolute max.
 */
export function resolveBoundedBodyCap(maxBytes: unknown): number {
  if (
    typeof maxBytes !== "number" ||
    !Number.isInteger(maxBytes) ||
    !Number.isSafeInteger(maxBytes) ||
    maxBytes < 1
  ) {
    return 1;
  }
  return maxBytes > MAX_BOUNDED_BODY_BYTES
    ? MAX_BOUNDED_BODY_BYTES
    : maxBytes;
}

/**
 * Read at most ``maxBytes`` from ``res.body``, canceling the reader when the
 * stream exceeds the cap. Prefers Content-Length early-reject when present.
 */
export async function readBoundedResponseText(
  res: Response,
  maxBytes: number,
): Promise<BoundedTextResult> {
  // Fail closed — Math.max(1, NaN)===NaN disables total>cap stream gate;
  // abs-cap so hostile SafeInteger maxBytes cannot OOM the stream buffer.
  const cap = resolveBoundedBodyCap(maxBytes);
  const lenHeader = res.headers.get("content-length");
  if (lenHeader != null && lenHeader.trim()) {
    const claimed = toNonNegativeSafeInt(lenHeader.trim(), -1);
    if (claimed < 0 || claimed > cap) {
      return { ok: false, reason: "too_large" };
    }
  }

  const reader = res.body?.getReader();
  if (!reader) {
    return { ok: true, text: "" };
  }

  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
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
    try {
      await reader.cancel();
    } catch {
      /* ignore */
    }
    return { ok: false, reason: "read_error" };
  }

  if (total === 0) {
    return { ok: true, text: "" };
  }

  const buf = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    buf.set(chunk, offset);
    offset += chunk.byteLength;
  }

  try {
    return {
      ok: true,
      text: new TextDecoder("utf-8", { fatal: true }).decode(buf),
    };
  } catch {
    return { ok: false, reason: "read_error" };
  }
}

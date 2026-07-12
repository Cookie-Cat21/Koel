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
 * Read at most ``maxBytes`` from ``res.body``, canceling the reader when the
 * stream exceeds the cap. Prefers Content-Length early-reject when present.
 */
export async function readBoundedResponseText(
  res: Response,
  maxBytes: number,
): Promise<BoundedTextResult> {
  const cap = Math.max(1, maxBytes);
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

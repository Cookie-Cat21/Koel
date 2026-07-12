/** Cap hostile timestamp strings before Date parse / egress. */
export const MAX_ISO_INPUT_LENGTH = 64;

/** ECMAScript Date absolute millisecond bound (±100M days from epoch). */
export const MAX_DATE_MS = 8.64e15;

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/;

function safeToIsoString(d: Date): string | null {
  const t = d.getTime();
  // Fail closed — NaN / out-of-range used to throw in toISOString.
  if (Number.isNaN(t) || Math.abs(t) > MAX_DATE_MS) return null;
  try {
    const iso = d.toISOString();
    // Cap egress length — expanded-year ISO must not balloon JSON / UI.
    if (!iso || iso.length > MAX_ISO_INPUT_LENGTH) return null;
    return iso;
  } catch {
    return null;
  }
}

/**
 * Normalize Postgres timestamptz / Date / string to ISO-8601 UTC.
 *
 * Medium fix: never raw-egress an unparseable string (poisoned DB / proxy
 * text used to balloon JSON and leak C0 into dash timestamps).
 * Also fail-closed on extreme Date/number values that used to throw in
 * ``toISOString`` or emit overlong expanded-year forms.
 */
export function toIso(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date) {
    return safeToIsoString(value);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return null;
    return safeToIsoString(new Date(value));
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed || trimmed.length > MAX_ISO_INPUT_LENGTH) return null;
    if (CTRL_RE.test(trimmed)) return null;
    return safeToIsoString(new Date(trimmed));
  }
  return null;
}

/** Normalize Postgres timestamptz / Date / string to ISO-8601 UTC. */
export function toIso(value: unknown): string | null {
  if (value == null) return null;
  if (value instanceof Date) return value.toISOString();
  if (typeof value === "string") {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toISOString();
  }
  return null;
}

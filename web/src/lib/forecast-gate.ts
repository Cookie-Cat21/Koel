/**
 * Shared helpers for selective forecast gates (Spoke / Silent UI).
 * Postgres-only metadata — not a trading signal.
 */

export function isSelectiveGate(gate: string | null | undefined): boolean {
  return (
    gate === "gated_p90" ||
    gate === "hpe_p90" ||
    gate === "gated_c55" ||
    gate === "gated"
  );
}

export function gateShortLabel(gate: string | null | undefined): string | null {
  if (gate === "gated_p90" || gate === "hpe_p90") return "Selective ~90%";
  if (gate === "gated_c55" || gate === "gated") return "Selective ~73%";
  if (gate === "always_on") return "Always-on ~60%";
  return null;
}

export function normalizeForecastGate(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const g = raw.trim().slice(0, 32);
  if (!g) return null;
  return g;
}

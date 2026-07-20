/**
 * Phase 3 scenario AI fence for the thin dashboard.
 *
 * Mirrors Python `koel.scenarios.scenarios_enabled`: only `AI_SCENARIOS_ENABLED=1`
 * opts in. No LLM / provider checks here — the dash page stays a stub either way.
 * Truthy lookalikes (`true` / `yes` / `on`) stay off so a loose env cannot
 * accidentally advertise the opted-in stub.
 */

export function scenariosEnabled(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  const raw = env.AI_SCENARIOS_ENABLED ?? "0";
  // Fail closed — non-string mock/hostile env values must not throw on .trim.
  if (typeof raw !== "string") return false;
  return raw.trim() === "1";
}

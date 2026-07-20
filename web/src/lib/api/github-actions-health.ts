/**
 * Public GitHub Actions snapshot for the Health page.
 * Fail-soft — never drives ok/degraded. Uses the public Actions API
 * (optional GITHUB_TOKEN for higher rate limits).
 */

import { toNonNegativeSafeInt } from "@/lib/api/safe-int";
import { toIso } from "@/lib/api/time";

export const HEALTH_GITHUB_REPO_DEFAULT = "ArdenoStudio/Koel";
/** Public Actions API can be slow from Vercel; keep fail-soft but give it room. */
export const HEALTH_CI_FETCH_TIMEOUT_MS = 8000;
/** Enough slots for CI + drain + ML + backfill workflows on Health. */
export const HEALTH_CI_RUNS_MAX = 14;
export const HEALTH_CI_STRING_MAX = 96;

/**
 * Ops workflows the Health checklist expects. Fetched one-latest each so a
 * CI flood of push/PR runs cannot push scheduled jobs out of the window.
 */
export const HEALTH_CI_WORKFLOW_FILES = [
  "ci.yml",
  "pdf-metrics-drain.yml",
  "macro-tick.yml",
  "market-tick.yml",
  "score-signals.yml",
  "ml-self-learn.yml",
  "path-backfill.yml",
  "appetite-backfill.yml",
  "sector-notices-backfill.yml",
] as const;

/** Legacy fork / old default — always resolve to the canonical Actions repo. */
const HEALTH_GITHUB_REPO_ALIASES: Record<string, string> = {
  "cookie-cat21/koel": HEALTH_GITHUB_REPO_DEFAULT,
  "cookie-cat21/chime": HEALTH_GITHUB_REPO_DEFAULT,
};

export type CiWorkflowRun = {
  workflow: string;
  status: string;
  conclusion: string | null;
  branch: string;
  event: string;
  run_number: number;
  html_url: string;
  updated_at: string | null;
};

export type CiHealthBlock = {
  repo: string;
  html_url: string;
  runs: CiWorkflowRun[];
  fetched_at: string;
  error?: string;
};

const CONCLUSION_ALLOW = new Set([
  "success",
  "failure",
  "cancelled",
  "skipped",
  "timed_out",
  "action_required",
  "neutral",
  "stale",
]);

const STATUS_ALLOW = new Set([
  "queued",
  "in_progress",
  "completed",
  "waiting",
  "requested",
  "pending",
]);

function cleanStr(raw: unknown, max = HEALTH_CI_STRING_MAX): string | null {
  if (typeof raw !== "string") return null;
  const cleaned = raw.replace(/[\u0000-\u001F\u007F-\u009F]/g, "").trim();
  if (!cleaned) return null;
  return cleaned.length > max ? cleaned.slice(0, max) : cleaned;
}

/** ``owner/repo`` only — reject path traversal / URLs. */
export function resolveHealthGithubRepo(raw: unknown): string {
  if (typeof raw !== "string") return HEALTH_GITHUB_REPO_DEFAULT;
  const trimmed = raw.trim();
  if (!trimmed || trimmed.length > 96) return HEALTH_GITHUB_REPO_DEFAULT;
  if (!/^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?\/[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$/.test(
    trimmed,
  )) {
    return HEALTH_GITHUB_REPO_DEFAULT;
  }
  // Fail closed — ``..`` segments must never reach the Actions URL builder.
  if (trimmed.includes("..")) return HEALTH_GITHUB_REPO_DEFAULT;
  const aliased = HEALTH_GITHUB_REPO_ALIASES[trimmed.toLowerCase()];
  if (aliased) return aliased;
  // Any other cookie-cat21/* env leftover → canonical org (same repo name).
  if (trimmed.toLowerCase().startsWith("cookie-cat21/")) {
    return HEALTH_GITHUB_REPO_DEFAULT;
  }
  return trimmed;
}

function pickLatestPerWorkflow(
  runs: CiWorkflowRun[],
  limit: number,
): CiWorkflowRun[] {
  const seen = new Set<string>();
  const out: CiWorkflowRun[] = [];
  for (const run of runs) {
    const key = run.workflow.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(run);
    if (out.length >= limit) break;
  }
  return out;
}

type GhRun = {
  name?: unknown;
  status?: unknown;
  conclusion?: unknown;
  head_branch?: unknown;
  event?: unknown;
  run_number?: unknown;
  html_url?: unknown;
  updated_at?: unknown;
  path?: unknown;
};

function parseGhRun(row: GhRun): CiWorkflowRun | null {
  if (!row || typeof row !== "object") return null;
  const workflow =
    cleanStr(row.name) ||
    cleanStr(row.path)?.replace(/\.ya?ml$/i, "") ||
    null;
  if (!workflow) return null;
  const statusRaw = cleanStr(row.status, 32)?.toLowerCase() ?? "";
  const status = STATUS_ALLOW.has(statusRaw) ? statusRaw : "unknown";
  const conclusionRaw = cleanStr(row.conclusion, 32)?.toLowerCase() ?? null;
  const conclusion =
    conclusionRaw && CONCLUSION_ALLOW.has(conclusionRaw)
      ? conclusionRaw
      : conclusionRaw
        ? "unknown"
        : null;
  const branch = cleanStr(row.head_branch, 64) ?? "—";
  const event = cleanStr(row.event, 32) ?? "—";
  const runNumber = toNonNegativeSafeInt(row.run_number, -1);
  if (runNumber < 0) return null;
  const url = cleanStr(row.html_url, 256);
  if (!url || !url.startsWith("https://github.com/")) return null;
  const updated = toIso(
    typeof row.updated_at === "string" ? row.updated_at : null,
  );
  return {
    workflow,
    status,
    conclusion,
    branch,
    event,
    run_number: runNumber,
    html_url: url,
    updated_at: updated,
  };
}

function parseWorkflowRunsPayload(json: unknown, maxRows: number): CiWorkflowRun[] {
  if (
    json == null ||
    typeof json !== "object" ||
    Array.isArray(json) ||
    !Array.isArray((json as { workflow_runs?: unknown }).workflow_runs)
  ) {
    return [];
  }
  const rawRuns = (json as { workflow_runs: GhRun[] }).workflow_runs;
  const parsed: CiWorkflowRun[] = [];
  for (const row of rawRuns) {
    const run = parseGhRun(row);
    if (!run) continue;
    parsed.push(run);
    if (parsed.length >= maxRows) break;
  }
  return parsed;
}

async function fetchRunsJson(
  url: string,
  fetchImpl: typeof fetch,
  headers: Record<string, string>,
  signal: AbortSignal,
): Promise<{ ok: boolean; status: number; json: unknown }> {
  const res = await fetchImpl(url, {
    method: "GET",
    signal,
    redirect: "follow",
    headers,
    // Cache briefly on the Next data cache when available.
    next: { revalidate: 60 },
  } as RequestInit);
  if (!res.ok) {
    return { ok: false, status: res.status, json: null };
  }
  return { ok: true, status: res.status, json: await res.json() };
}

/** Opt out with ``HEALTH_GITHUB_ACTIONS=0`` (unit harness / air-gapped). */
export function githubActionsHealthEnabled(): boolean {
  const raw = process.env.HEALTH_GITHUB_ACTIONS;
  if (typeof raw === "string" && raw.trim() === "0") return false;
  return true;
}

/**
 * Fetch recent Actions runs. Prefer one row per known workflow file so the
 * Health checklist is not drowned by CI push/PR noise in a global window.
 */
export async function queryGithubActionsHealth(
  fetchImpl: typeof fetch = fetch,
): Promise<CiHealthBlock | null> {
  if (!githubActionsHealthEnabled()) return null;
  const repo = resolveHealthGithubRepo(process.env.HEALTH_GITHUB_REPO);
  const htmlUrl = `https://github.com/${repo}/actions`;
  const fetchedAt = new Date().toISOString();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), HEALTH_CI_FETCH_TIMEOUT_MS);
  try {
    const headers: Record<string, string> = {
      Accept: "application/vnd.github+json",
      "User-Agent": "koel-health",
      "X-GitHub-Api-Version": "2022-11-28",
    };
    const tokenEnv = process.env.GITHUB_TOKEN;
    const token =
      typeof tokenEnv === "string" && tokenEnv.trim()
        ? tokenEnv.trim()
        : typeof process.env.GH_TOKEN === "string" && process.env.GH_TOKEN.trim()
          ? process.env.GH_TOKEN.trim()
          : "";
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const base = `https://api.github.com/repos/${repo}/actions`;
    const requests = [
      fetchRunsJson(`${base}/runs?per_page=30`, fetchImpl, headers, ctrl.signal),
      ...HEALTH_CI_WORKFLOW_FILES.map((file) =>
        fetchRunsJson(
          `${base}/workflows/${encodeURIComponent(file)}/runs?per_page=1`,
          fetchImpl,
          headers,
          ctrl.signal,
        ),
      ),
    ];
    const results = await Promise.all(requests);

    const globalRes = results[0];
    if (!globalRes?.ok) {
      // Per-workflow alone can still populate the checklist.
      const anyWorkflowOk = results.slice(1).some((r) => r.ok);
      if (!anyWorkflowOk) {
        return {
          repo,
          html_url: htmlUrl,
          runs: [],
          fetched_at: fetchedAt,
          error: `github_http_${globalRes?.status ?? 0}`,
        };
      }
    }

    // Per-workflow latest first so CI noise in the global page cannot win.
    const perWorkflow: CiWorkflowRun[] = [];
    for (const res of results.slice(1)) {
      if (!res.ok) continue;
      perWorkflow.push(...parseWorkflowRunsPayload(res.json, 1));
    }
    const globalRuns = globalRes?.ok
      ? parseWorkflowRunsPayload(globalRes.json, 40)
      : [];
    const merged = pickLatestPerWorkflow(
      [...perWorkflow, ...globalRuns],
      HEALTH_CI_RUNS_MAX,
    );

    if (merged.length === 0 && !globalRes?.ok) {
      return {
        repo,
        html_url: htmlUrl,
        runs: [],
        fetched_at: fetchedAt,
        error: `github_http_${globalRes?.status ?? 0}`,
      };
    }

    return {
      repo,
      html_url: htmlUrl,
      runs: merged,
      fetched_at: fetchedAt,
    };
  } catch {
    return {
      repo,
      html_url: htmlUrl,
      runs: [],
      fetched_at: fetchedAt,
      error: "github_unreachable",
    };
  } finally {
    clearTimeout(timer);
  }
}

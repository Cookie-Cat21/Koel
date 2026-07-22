/** Canonical filing category tags (parity with koel/filing_categories.py). */

export const FILING_CATEGORY_TAGS = [
  "results",
  "board",
  "corporate_action",
  "shareholding",
  "other",
] as const;

export type FilingCategoryTag = (typeof FILING_CATEGORY_TAGS)[number];

const TAG_SET = new Set<string>(FILING_CATEGORY_TAGS);

export const FILING_CATEGORY_LABELS: Record<FilingCategoryTag, string> = {
  results: "Results / financials",
  board: "Board / directors",
  corporate_action: "Corporate actions",
  shareholding: "Shareholding / insider",
  other: "Other filings",
};

export function normalizeFilingTags(raw: unknown): FilingCategoryTag[] {
  const parts: string[] = [];
  if (typeof raw === "string") {
    parts.push(...raw.split(",").map((s) => s.trim()));
  } else if (Array.isArray(raw)) {
    for (const item of raw) {
      if (typeof item === "string") parts.push(item.trim());
    }
  }
  const out: FilingCategoryTag[] = [];
  const seen = new Set<string>();
  for (const p of parts) {
    const tag = p.toLowerCase().replace(/[\s-]+/g, "_");
    if (!TAG_SET.has(tag) || seen.has(tag)) continue;
    seen.add(tag);
    out.push(tag as FilingCategoryTag);
  }
  return out;
}

const RESULTS_RE =
  /\b(interim|annual|quarter|q[1-4]|financial\s+statement|earnings|results?|profit|eps)\b/i;
const BOARD_RE =
  /\b(board\s+meeting|directors?|appointment|resignation|outcome\s+of\s+board)\b/i;
const CA_RE =
  /\b(dividend|bonus|split|rights?|subdivision|consolidation|capital\s+reduction|buy[\s-]?back)\b/i;
const SH_RE =
  /\b(shareholding|substantial\s+share|director.?s?\s+deal|insider|promoter|pledge)\b/i;

export function classifyFiling(
  category: string | null | undefined,
  title: string | null | undefined,
): FilingCategoryTag {
  const hay = [category ?? "", title ?? ""].filter(Boolean).join(" ").trim();
  if (!hay) return "other";
  if (RESULTS_RE.test(hay)) return "results";
  if (BOARD_RE.test(hay)) return "board";
  if (CA_RE.test(hay)) return "corporate_action";
  if (SH_RE.test(hay)) return "shareholding";
  return "other";
}

/**
 * Soft-merge keys for CSE directors with split initials spellings.
 * Display stays as CSE initials — not common/public first names.
 * Keep merge keys in sync with koel/extractors/person_aliases.py
 */

/** Normalized uppercase name (dots → spaces) → merge key */
const MERGE_BY_COMPACT: Record<string, string> = {
  "K A D D PERERA": "kadd_perera",
  "M PANDITHAGE": "m_pandithage",
  "A M PANDITHAGE": "m_pandithage",
  "K BALENDRA": "k_balendra",
  "K N J BALENDRA": "k_balendra",
  "J G A COORAY": "jga_cooray",
  "D S T JAYAWARDENA": "dst_jayawardena",
  "DON S T JAYAWARDENA": "dst_jayawardena",
  "D HASITHA S JAYAWARDENA": "hasitha_jayawardena",
  "D HASITHA STASSEN JAYAWARDENA": "hasitha_jayawardena",
  "I C NANAYAKKARA": "ic_nanayakkara",
  "W D K JAYAWARDENA": "wdk_jayawardena",
  "H A S MADANAYAKE": "has_madanayake",
  "U G MADANAYAKE": "ug_madanayake",
  "S K SHAH": "sk_shah",
  "S H AMARASEKERA": "sh_amarasekera",
  "D A CABRAAL": "da_cabraal",
};

export function compactPersonName(name: string): string {
  return name
    .replace(/\./g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase();
}

function mergeKeyFor(name: string): string | null {
  const compact = compactPersonName(name);
  return MERGE_BY_COMPACT[compact] ?? null;
}

/** Prefer CSE-style initials labels over given-name forms when merging. */
export function preferredDisplayName(name: string): string {
  return name;
}

/** When soft-merging two labels, keep the more initials-like CSE form. */
export function pickInitialsDisplay(a: string, b: string): string {
  const score = (n: string) => {
    const parts = compactPersonName(n).split(/\s+/).filter(Boolean);
    if (parts.length < 2) return 0;
    // Heavily prefer names whose "given" tokens are single-letter initials
    const initials = parts.slice(0, -1).filter((p) => p.length === 1).length;
    const longGiven = parts.slice(0, -1).filter((p) => p.length > 2).length;
    return initials * 20 - longGiven * 15 + Math.min(n.length, 24);
  };
  return score(a) >= score(b) ? a : b;
}

/** Soft-merge key — collapses known CSE spelling variants only. */
export function softPersonKey(name: string): string {
  const merge = mergeKeyFor(name);
  if (merge) return `ALIAS:${merge.toUpperCase()}`;
  const compact = compactPersonName(name);
  const parts = compact.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return compact;
  const last = parts[parts.length - 1];
  const initials = parts
    .slice(0, -1)
    .map((p) => p[0] ?? "")
    .join("");
  return `${initials}:${last}`;
}

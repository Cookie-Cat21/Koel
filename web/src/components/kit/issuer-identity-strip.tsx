import { Badge } from "@/components/ui/badge";
import { HelpLink } from "@/components/help-link";
import { formatCompactNumber, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export type IssuerIdentity = {
  isin: string | null;
  board_type: string | null;
  founded: string | null;
  fin_year_end: string | null;
  website: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  auditors: string | null;
  secretaries: string | null;
  business_summary: string | null;
  beta_aspi: number | null;
  beta_sl20: number | null;
  beta_period: string | null;
  market_cap_pct: number | null;
  shares_issued: number | null;
  par_value: number | null;
  top_posts: { name: string; role: string }[];
};

function safeExternalHref(raw: string | null): string | null {
  if (!raw || typeof raw !== "string") return null;
  const t = raw.trim();
  if (!t) return null;
  if (/^https?:\/\//i.test(t)) return t;
  if (/^www\./i.test(t)) return `https://${t}`;
  // Bare domains like combank.lk — only allow hostname-ish
  if (/^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}(\/.*)?$/i.test(t)) {
    return `https://${t}`;
  }
  return null;
}

function fmtBeta(v: number | null): string | null {
  if (v == null || !Number.isFinite(v)) return null;
  return v.toFixed(2);
}

/**
 * CSE registry identity — ISIN, board, beta, contact (from issuer_profiles).
 * HyperUI / shadcn Badge chips — not a Tremor KPI wall.
 */
export function IssuerIdentityStrip({
  profile,
  className,
}: {
  profile: IssuerIdentity | null;
  className?: string;
}) {
  if (!profile) return null;

  const chips: { key: string; label: string }[] = [];
  if (profile.isin) chips.push({ key: "isin", label: `ISIN ${profile.isin}` });
  if (profile.board_type)
    chips.push({ key: "board", label: profile.board_type });
  if (profile.founded)
    chips.push({ key: "founded", label: `Founded ${profile.founded}` });
  const betaA = fmtBeta(profile.beta_aspi);
  const betaS = fmtBeta(profile.beta_sl20);
  if (betaA)
    chips.push({
      key: "beta-aspi",
      label: `β ASPI ${betaA}${profile.beta_period ? ` (${profile.beta_period})` : ""}`,
    });
  if (betaS) chips.push({ key: "beta-sl20", label: `β SL20 ${betaS}` });
  if (profile.market_cap_pct != null && Number.isFinite(profile.market_cap_pct)) {
    chips.push({
      key: "mcap-pct",
      label: `${formatNumber(profile.market_cap_pct, 2)}% of market`,
    });
  }
  if (profile.shares_issued != null) {
    chips.push({
      key: "shares",
      label: `${formatCompactNumber(profile.shares_issued)} shares`,
    });
  }
  if (profile.par_value != null) {
    chips.push({
      key: "par",
      label: `Par ${formatNumber(profile.par_value)}`,
    });
  }

  const webHref = safeExternalHref(profile.website);
  const hasBody =
    chips.length > 0 ||
    Boolean(profile.business_summary) ||
    Boolean(profile.address) ||
    Boolean(profile.auditors) ||
    profile.top_posts.length > 0;

  if (!hasBody) return null;

  return (
    <section
      className={cn(
        "mt-4 rounded-xl border border-border/70 bg-background px-5 py-4 sm:px-6",
        className,
      )}
      aria-label="Issuer identity"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Issuer
        </h2>
        <HelpLink
          topic="symbol-issuer"
          variant="text"
          className="text-[11px] text-muted-foreground"
        >
          Source
        </HelpLink>
      </div>

      {chips.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2" role="list">
          {chips.map((c) => (
            <Badge
              key={c.key}
              variant="outline"
              className="font-mono text-[11px] font-normal tabular-nums"
              role="listitem"
            >
              {c.label}
            </Badge>
          ))}
        </div>
      ) : null}

      {profile.business_summary ? (
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          {profile.business_summary}
        </p>
      ) : null}

      {profile.top_posts.length > 0 ? (
        <ul className="mt-3 space-y-1 text-sm">
          {profile.top_posts.slice(0, 6).map((p, i) => (
            <li key={`${p.name}-${i}`} className="text-muted-foreground">
              <span className="font-medium text-foreground">{p.name}</span>
              {p.role ? (
                <span className="text-muted-foreground"> — {p.role}</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        {profile.auditors ? (
          <div>
            <dt className="text-xs text-muted-foreground">Auditors</dt>
            <dd className="text-foreground">{profile.auditors}</dd>
          </div>
        ) : null}
        {profile.secretaries ? (
          <div>
            <dt className="text-xs text-muted-foreground">Secretaries</dt>
            <dd className="text-foreground">{profile.secretaries}</dd>
          </div>
        ) : null}
        {profile.address ? (
          <div className="sm:col-span-2">
            <dt className="text-xs text-muted-foreground">Address</dt>
            <dd className="text-foreground">{profile.address}</dd>
          </div>
        ) : null}
        {profile.phone ? (
          <div>
            <dt className="text-xs text-muted-foreground">Phone</dt>
            <dd className="font-mono tabular-nums text-foreground">
              {profile.phone}
            </dd>
          </div>
        ) : null}
        {profile.email ? (
          <div>
            <dt className="text-xs text-muted-foreground">Email</dt>
            <dd>
              <a
                href={`mailto:${profile.email}`}
                className="text-foreground underline underline-offset-4"
              >
                {profile.email}
              </a>
            </dd>
          </div>
        ) : null}
        {webHref ? (
          <div>
            <dt className="text-xs text-muted-foreground">Website</dt>
            <dd>
              <a
                href={webHref}
                target="_blank"
                rel="noopener noreferrer"
                className="text-foreground underline underline-offset-4"
              >
                {profile.website}
              </a>
            </dd>
          </div>
        ) : null}
        {profile.fin_year_end ? (
          <div>
            <dt className="text-xs text-muted-foreground">
              Financial year end (CSE code)
            </dt>
            <dd className="font-mono tabular-nums text-foreground">
              {profile.fin_year_end}
            </dd>
          </div>
        ) : null}
      </dl>
      <p className="mt-3 text-[11px] text-muted-foreground">
        From public CSE issuer JSON cached in Postgres — not financial advice.
      </p>
    </section>
  );
}

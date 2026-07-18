import { HugeiconsIcon } from "@hugeicons/react";
import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons";

import { KoelMark } from "@/components/brand/koel-brand";
import { NFA_FOOTER } from "@/lib/nfa";

/**
 * Footer-20 (watermelon.sh registry), adapted for koel: brand chrome, NFA
 * disclaimer, no scroll-triggered fade (legal links must stay visible), and
 * one continuous gradient wash masked by the lowercase wordmark.
 */

type FooterLink = { label: string; href: string; external?: boolean };

/** Inter Display Black outlines for "koel" (font units, tight crop). */
const KOEL_WATERMARK_PATHS = [
  "M242.4 1732.4V242.4H642.4V1020.4H646.4L914.4 676.4H1366.4L994.4 1140.4L1378.4 1732.4H924.4L700.4 1367.4L642.4 1439.4V1732.4Z",
  "M1980.4 1756.4Q1809.4 1756.4 1679.4 1688.9Q1549.4 1621.4 1476.9 1497.4Q1404.4 1373.4 1404.4 1204.4Q1404.4 1035.4 1476.9 911.9Q1549.4 788.4 1679.4 720.4Q1809.4 652.4 1980.4 652.4Q2152.4 652.4 2281.9 720.4Q2411.4 788.4 2483.9 911.9Q2556.4 1035.4 2556.4 1204.4Q2556.4 1373.4 2483.9 1497.4Q2411.4 1621.4 2281.9 1688.9Q2152.4 1756.4 1980.4 1756.4ZM1980.4 1444.4Q2051.4 1444.4 2101.9 1383.9Q2152.4 1323.4 2152.4 1204.4Q2152.4 1085.4 2101.9 1024.9Q2051.4 964.4 1980.4 964.4Q1909.4 964.4 1858.9 1024.9Q1808.4 1085.4 1808.4 1204.4Q1808.4 1323.4 1858.9 1383.9Q1909.4 1444.4 1980.4 1444.4Z",
  "M3209.4 1756.4Q3045.4 1756.4 2918.4 1685.9Q2791.4 1615.4 2719.9 1490.4Q2648.4 1365.4 2648.4 1204.4Q2648.4 1042.4 2719.4 917.9Q2790.4 793.4 2914.9 722.9Q3039.4 652.4 3201.4 652.4Q3363.4 652.4 3488.4 721.4Q3613.4 790.4 3683.9 912.4Q3754.4 1034.4 3754.4 1193.4V1300.4H3036.4Q3038.4 1384.4 3088.4 1431.4Q3138.4 1478.4 3225.4 1478.4Q3289.4 1478.4 3334.9 1454.4Q3380.4 1430.4 3396.4 1387.4H3750.4Q3731.4 1495.4 3655.4 1578.4Q3579.4 1661.4 3463.9 1708.9Q3348.4 1756.4 3209.4 1756.4ZM3039.4 1076.4H3385.4Q3375.4 1011.4 3330.4 974.9Q3285.4 938.4 3212.4 938.4Q3139.4 938.4 3094.4 974.9Q3049.4 1011.4 3039.4 1076.4Z",
  "M4282.4 242.4V1732.4H3882.4V242.4Z",
] as const;

export function KoelFooter({
  telegramHref,
  className,
}: {
  telegramHref?: string | null;
  className?: string;
}) {
  const product: FooterLink[] = [
    { label: "Home", href: "/" },
    { label: "How it works", href: "/#how-it-works" },
    { label: "Pricing", href: "/pricing" },
    { label: "Blog", href: "/blog" },
  ];
  const legal: FooterLink[] = [
    { label: "Terms", href: "/legal/terms" },
    { label: "Privacy", href: "/legal/privacy" },
    { label: "Sign in", href: "/login" },
  ];
  const elsewhere: FooterLink[] = telegramHref
    ? [{ label: "Telegram", href: telegramHref, external: true }]
    : [];

  return (
    <footer
      className={`relative w-full overflow-hidden rounded-t-3xl border-t border-border bg-background text-muted-foreground font-sans ${className ?? ""}`}
    >
      <div className="relative z-10 mx-auto flex w-full max-w-[1400px] flex-col justify-between border-x border-dashed border-border px-6 pt-20 md:px-12 md:pt-32 lg:px-16">
        <div className="mb-10 grid grid-cols-1 gap-16 md:mb-16 lg:mb-24 lg:grid-cols-12 lg:gap-8">
          <div className="lg:col-span-5 xl:col-span-4 flex flex-col gap-6 md:gap-8">
            <div className="flex items-center gap-2 text-foreground">
              <KoelMark size="sm" />
              <span className="mt-0.5 text-lg font-medium tracking-wide">
                koel
              </span>
            </div>

            <p className="max-w-[320px] text-[15px] leading-relaxed text-muted-foreground">
              Telegram-first CSE alerts. Watch symbols, set rules in a thin
              dash — the ping is the product.
            </p>

            <p className="max-w-[320px] text-xs leading-relaxed text-muted-foreground/70">
              {NFA_FOOTER}
            </p>

            {telegramHref ? (
              <a
                href={telegramHref}
                target="_blank"
                rel="noopener noreferrer"
                className="group mt-2 inline-flex items-center gap-2 text-[17px] text-foreground/90 transition-colors hover:text-foreground"
              >
                Open Telegram bot
                <HugeiconsIcon
                  icon={ArrowUpRight01Icon}
                  size={18}
                  className="text-muted-foreground transition-colors group-hover:text-foreground"
                />
              </a>
            ) : null}
          </div>

          <div className="lg:col-span-7 xl:col-span-8 grid grid-cols-2 gap-12 sm:grid-cols-3 lg:gap-8">
            <div className="flex flex-col gap-6">
              <h4 className="font-medium text-foreground">Product</h4>
              <ul className="flex flex-col gap-3">
                {product.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-[15px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            <div className="flex flex-col gap-6">
              <h4 className="font-medium text-foreground">Legal</h4>
              <ul className="flex flex-col gap-3">
                {legal.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-[15px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            {elsewhere.length > 0 ? (
              <div className="flex flex-col gap-6">
                <h4 className="font-medium text-foreground">Elsewhere</h4>
                <ul className="flex flex-col gap-3">
                  {elsewhere.map((link) => (
                    <li key={link.label}>
                      <a
                        href={link.href}
                        target={link.external ? "_blank" : undefined}
                        rel={link.external ? "noopener noreferrer" : undefined}
                        className="text-[15px] text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </div>

        {/* Oversized Footer-20 watermark. One userSpaceOnUse wash masked by the
            wordmark — not per-glyph objectBoundingBox fills (those repeat). */}
        <div className="flex w-full justify-center pb-0 md:mt-auto">
          <svg
            className="h-auto w-full select-none"
            viewBox="0 240 4525 1550"
            preserveAspectRatio="xMidYMid slice"
            aria-label="koel"
            role="img"
          >
            <defs>
              <linearGradient
                id="koel-watermark-gradient"
                gradientUnits="userSpaceOnUse"
                x1="0"
                y1="240"
                x2="4525"
                y2="1790"
              >
                <stop offset="0%" stopColor="#F7D7DE" />
                <stop offset="48%" stopColor="#E4D2F2" />
                <stop offset="100%" stopColor="#D5E3F6" />
              </linearGradient>
              <mask
                id="koel-watermark-mask"
                maskUnits="userSpaceOnUse"
                x="0"
                y="0"
                width="4525"
                height="1999"
              >
                <g fill="#fff">
                  {KOEL_WATERMARK_PATHS.map((d) => (
                    <path key={d.slice(0, 24)} d={d} />
                  ))}
                </g>
              </mask>
            </defs>
            <rect
              x="0"
              y="240"
              width="4525"
              height="1550"
              fill="url(#koel-watermark-gradient)"
              mask="url(#koel-watermark-mask)"
            />
          </svg>
        </div>
      </div>
    </footer>
  );
}

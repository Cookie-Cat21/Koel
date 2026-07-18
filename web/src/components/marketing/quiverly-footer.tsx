import { HugeiconsIcon } from "@hugeicons/react";
import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons";

import { QuiverlyMark } from "@/components/brand/quiverly-brand";
import { NFA_FOOTER } from "@/lib/nfa";

/**
 * Footer-20 (watermelon.sh registry), adapted for Quiverly: swaps the vendor
 * logo/copy for our brand, drops the placeholder email (no support inbox
 * yet), folds in the NFA disclaimer required near any price-adjacent
 * chrome, drops the original's scroll-triggered fade-in (could settle
 * mid-transition instead of reliably reaching full visibility — not
 * acceptable for legal/Terms links), and swaps the vendor's hardcoded
 * neutral-N and hex colors (plus dark: variants that never activate —
 * this site has no dark-mode toggle) for the same semantic theme tokens
 * (bg-background/text-foreground/border-border) every other page uses.
 */

type FooterLink = { label: string; href: string; external?: boolean };

export function QuiverlyFooter({
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
      className={`relative w-full bg-background text-muted-foreground font-sans overflow-hidden flex flex-col justify-between border-t border-border ${className ?? ""}`}
    >
      <div className="relative z-10 max-w-[1400px] w-full mx-auto px-6 md:px-12 lg:px-16 pt-20 md:pt-32 flex flex-col border-x border-dashed border-border">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-16 lg:gap-8 mb-10 md:mb-16 lg:mb-24">
          <div className="lg:col-span-5 xl:col-span-4 flex flex-col gap-6 md:gap-8">
            <div className="flex items-center gap-2 text-foreground">
              <QuiverlyMark size="sm" />
              <span className="font-medium tracking-wide text-lg mt-0.5">
                Quiverly
              </span>
            </div>

            <p className="text-[15px] leading-relaxed text-muted-foreground max-w-[320px]">
              Telegram-first CSE alerts. Watch symbols, set rules in a thin
              dash — the ping is the product.
            </p>

            <p className="text-xs leading-relaxed text-muted-foreground/70 max-w-[320px]">
              {NFA_FOOTER}
            </p>

            {telegramHref ? (
              <a
                href={telegramHref}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-[17px] text-foreground/90 hover:text-foreground transition-colors group mt-2"
              >
                Open Telegram bot
                <HugeiconsIcon
                  icon={ArrowUpRight01Icon}
                  size={18}
                  className="text-muted-foreground group-hover:text-foreground transition-colors"
                />
              </a>
            ) : null}
          </div>

          <div className="lg:col-span-7 xl:col-span-8 grid grid-cols-2 sm:grid-cols-3 gap-12 lg:gap-8">
            <div className="flex flex-col gap-6">
              <h4 className="font-medium text-foreground">Product</h4>
              <ul className="flex flex-col gap-3">
                {product.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-[15px] text-muted-foreground hover:text-foreground transition-colors"
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
                      className="text-[15px] text-muted-foreground hover:text-foreground transition-colors"
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
                        className="text-[15px] text-muted-foreground hover:text-foreground transition-colors"
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
        <div className="w-full flex justify-center md:mt-auto pb-0">
          <svg
            className="w-full h-auto select-none"
            viewBox="712 774 176 40"
            preserveAspectRatio="xMidYMid slice"
            aria-label="quiverly"
            role="img"
          >
            <defs>
              <linearGradient
                id="quiverly-watermark-gradient"
                gradientUnits="userSpaceOnUse"
                x1="712"
                y1="774"
                x2="888"
                y2="814"
              >
                <stop offset="0%" stopColor="#F7D7DE" />
                <stop offset="48%" stopColor="#E4D2F2" />
                <stop offset="100%" stopColor="#D5E3F6" />
              </linearGradient>
              <mask
                id="quiverly-watermark-mask"
                maskUnits="userSpaceOnUse"
                x="712"
                y="774"
                width="176"
                height="52"
              >
                <g fill="#fff">
                  <g transform="translate(714.8933,812.1581) scale(0.021424,-0.021424)">
                    <path d="M1141 -418H881V177H870Q849 137 811.0 91.0Q773 45 709.5 12.5Q646 -20 550 -20Q418 -20 313.5 47.5Q209 115 149.0 244.0Q89 373 89 557Q89 743 150.0 871.5Q211 1000 315.5 1066.0Q420 1132 549 1132Q649 1132 712.5 1098.5Q776 1065 813.0 1018.5Q850 972 870 933H886V1118H1141ZM621 194Q748 194 817.0 294.5Q886 395 886 558Q886 721 817.5 819.5Q749 918 621 918Q489 918 422.0 816.0Q355 714 355 558Q355 401 422.5 297.5Q490 194 621 194Z" />
                  </g>
                  <g transform="translate(741.8446,812.1581) scale(0.021424,-0.021424)">
                    <path d="M521 -14Q348 -14 243.0 96.0Q138 206 138 407V1118H398V447Q398 335 456.5 271.0Q515 207 617 207Q721 207 788.0 274.0Q855 341 855 463V1118H1116V0H869L867 224Q767 -14 521 -14Z" />
                  </g>
                  <g transform="translate(768.2818,812.1581) scale(0.021424,-0.021424)">
                    <path d="M138 0V1118H398V0ZM268 1276Q206 1276 161.5 1317.5Q117 1359 117 1419Q117 1478 161.5 1519.5Q206 1561 268 1561Q331 1561 375.5 1519.5Q420 1478 420 1419Q420 1359 375.5 1317.5Q331 1276 268 1276Z" />
                  </g>
                  <g transform="translate(779.3366,812.1581) scale(0.021424,-0.021424)">
                    <path d="M455 0 39 1118H317L521 510Q546 436 565.5 361.0Q585 286 604 210Q622 286 641.0 361.0Q660 436 685 510L888 1118H1164L746 0Z" />
                  </g>
                  <g transform="translate(804.6597,812.1581) scale(0.021424,-0.021424)">
                    <path d="M632 -23Q463 -23 341.5 48.0Q220 119 154.5 248.0Q89 377 89 552Q89 724 153.5 854.5Q218 985 336.5 1058.5Q455 1132 615 1132Q751 1132 867.5 1072.5Q984 1013 1055.0 888.5Q1126 764 1126 568V486H348Q353 337 431.5 259.0Q510 181 635 181Q721 181 782.5 218.0Q844 255 870 326L1109 277Q1069 142 943.5 59.5Q818 -23 632 -23ZM349 663H873Q861 783 796.5 855.5Q732 928 616 928Q497 928 427.5 851.5Q358 775 349 663Z" />
                  </g>
                  <g transform="translate(830.1757,812.1581) scale(0.021424,-0.021424)">
                    <path d="M138 0V1118H390V931H402Q432 1028 507.0 1080.5Q582 1133 678 1133Q728 1133 773 1126V887Q757 891 721.0 895.5Q685 900 650 900Q541 900 469.5 832.5Q398 765 398 658V0Z" />
                  </g>
                  <g transform="translate(847.1649,812.1581) scale(0.021424,-0.021424)">
                    <path d="M398 1490V0H138V1490Z" />
                  </g>
                  <g transform="translate(858.2196,812.1581) scale(0.021424,-0.021424)">
                    <path d="M127 -399 188 -196 219 -204Q307 -228 366.0 -199.5Q425 -171 445 -75L461 -4L39 1118H317L521 510Q545 437 563.0 364.5Q581 292 597 219Q616 293 635.5 365.5Q655 438 680 510L891 1118H1166L686 -144Q635 -278 544.0 -352.0Q453 -426 301 -426Q246 -426 199.5 -418.0Q153 -410 127 -399Z" />
                  </g>
                </g>
              </mask>
            </defs>
            <rect
              x="712"
              y="774"
              width="176"
              height="40"
              fill="url(#quiverly-watermark-gradient)"
              mask="url(#quiverly-watermark-mask)"
            />
          </svg>
        </div>
      </div>
    </footer>
  );
}

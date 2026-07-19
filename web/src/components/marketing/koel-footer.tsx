import { HugeiconsIcon } from "@hugeicons/react";
import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons";

import { KoelLockup } from "@/components/brand/koel-brand";
import { NFA_FOOTER } from "@/lib/nfa";

/**
 * Footer-20 (watermelon.sh registry), adapted for koel: brand chrome, NFA
 * disclaimer, no scroll-triggered fade (legal links must stay visible), and
 * one continuous gradient wash masked by the lowercase wordmark.
 */

type FooterLink = { label: string; href: string; external?: boolean };

/** Inter Display Black outlines for "koel" (font units, tight crop). */
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
            <div className="text-foreground">
              <KoelLockup size="sm" />
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
            viewBox="0 8.27 475 190.32"
            preserveAspectRatio="xMidYMid slice"
            aria-label="koel"
            role="img"
          >
            <defs>
              <linearGradient
                id="koel-watermark-gradient"
                gradientUnits="userSpaceOnUse"
                x1="0"
                y1="8.27"
                x2="475"
                y2="198.6"
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
                width="475"
                height="206.87"
              >
                <g transform="translate(-14.000000,221.000000) scale(0.100000,-0.100000)"
fill="#fff" stroke="none">
<path d="M140 1190 l0 -1020 195 0 195 0 1 193 1 192 54 49 53 48 247 -241
248 -241 250 0 250 0 -69 73 c-38 39 -202 205 -363 368 l-294 296 64 60 c35
33 190 178 346 322 155 144 282 264 282 266 0 3 -109 5 -242 5 l-243 -1 -285
-269 c-157 -148 -288 -269 -292 -269 -5 -1 -8 267 -8 594 l0 595 -195 0 -195
0 0 -1020z M4500 1190 l0 -1020 195 0 195 0 0 1020 0 1020 -195 0 -195 0 0
-1020z M2175 1581 c-85 -14 -137 -31 -220 -71 -378 -182 -517 -648 -303 -1015
62 -105 185 -221 289 -273 182 -89 371 -105 548 -45 232 78 402 249 478 483
23 72 27 102 27 195 0 134 -17 206 -81 335 -39 80 -60 109 -133 181 -70 70
-103 94 -180 132 -140 69 -300 98 -425 78z m233 -421 c155 -67 230 -277 157
-438 -44 -97 -110 -151 -217 -178 -79 -20 -149 -12 -227 27 -109 54 -165 152
-166 289 0 92 10 128 57 197 82 122 251 166 396 103z M3606 1575 c-284 -54
-505 -266 -577 -555 -18 -74 -16 -239 5 -320 55 -222 224 -414 438 -499 216
-87 455 -78 658 24 120 60 255 181 234 210 -5 8 -74 64 -154 125 l-144 110
-41 -39 c-22 -21 -57 -48 -78 -59 -58 -30 -163 -46 -232 -36 l-58 9 381 274
c210 150 382 278 382 284 0 6 -16 42 -35 81 -139 283 -470 448 -779 391z m257
-415 c26 -12 46 -26 45 -31 -2 -4 -111 -85 -243 -179 l-240 -170 -6 43 c-24
159 79 314 236 358 52 14 156 4 208 -21z"/>
</g>
              </mask>
            </defs>
            <rect
              x="0"
              y="8.27"
              width="475"
              height="190.32"
              fill="url(#koel-watermark-gradient)"
              mask="url(#koel-watermark-mask)"
            />
          </svg>
        </div>
      </div>
    </footer>
  );
}

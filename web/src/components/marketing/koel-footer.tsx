import { HugeiconsIcon } from "@hugeicons/react";
import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons";

import { KoelMark, KoelWordmark } from "@/components/brand/koel-brand";
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
            <div className="flex items-center gap-2 text-foreground">
              <KoelMark size="sm" />
              <KoelWordmark size="sm" />
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
            viewBox="0 10.34 475 186.16"
            preserveAspectRatio="xMidYMid slice"
            aria-label="koel"
            role="img"
          >
            <defs>
              <linearGradient
                id="koel-watermark-gradient"
                gradientUnits="userSpaceOnUse"
                x1="0"
                y1="10.34"
                x2="475"
                y2="196.5"
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
                height="206.84"
              >
                <g transform="translate(-28,235) scale(0.1,-0.1)"
fill="#fff" stroke="none">
<path d="M280 1330 l0 -1020 195 0 195 0 0 188 0 188 55 54 54 53 246 -241
245 -242 252 0 252 0 -35 38 c-18 20 -179 184 -356 363 -178 180 -323 331
-323 337 0 6 152 151 338 323 185 172 339 316 340 321 2 4 -106 8 -240 8
l-243 -1 -290 -271 -290 -271 -3 596 -2 597 -195 0 -195 0 0 -1020z M4640
1330 l0 -1020 195 0 195 0 0 1020 0 1020 -195 0 -195 0 0 -1020z M2308 1720
c-283 -51 -498 -233 -586 -497 -23 -69 -26 -93 -26 -218 0 -123 4 -149 26
-217 41 -122 92 -204 187 -298 101 -101 202 -157 346 -191 203 -48 438 7 607
142 246 197 336 507 233 802 -38 107 -80 172 -175 267 -96 97 -193 154 -320
190 -85 23 -223 33 -292 20z m235 -418 c61 -27 123 -86 155 -146 24 -46 27
-61 27 -156 0 -90 -3 -111 -23 -148 -61 -115 -163 -176 -292 -176 -94 0 -159
27 -223 92 -57 58 -86 122 -94 205 -14 154 84 304 224 343 62 18 169 11 226
-14z M3727 1711 c-335 -73 -571 -361 -571 -696 0 -132 16 -200 74 -320 79
-164 207 -284 380 -355 229 -95 509 -73 721 56 63 38 179 147 179 168 0 7 -68
65 -151 130 l-151 116 -50 -44 c-69 -63 -142 -89 -250 -90 -77 0 -111 6 -97
18 2 2 172 124 377 271 427 306 393 263 319 395 -148 266 -482 416 -780 351z
m276 -411 c26 -12 47 -25 47 -29 0 -3 -109 -83 -243 -178 l-242 -172 -3 76
c-4 110 16 163 92 239 48 47 73 64 116 77 73 22 170 17 233 -13z"/>
</g>
              </mask>
            </defs>
            <rect
              x="0"
              y="10.34"
              width="475"
              height="186.16"
              fill="url(#koel-watermark-gradient)"
              mask="url(#koel-watermark-mask)"
            />
          </svg>
        </div>
      </div>
    </footer>
  );
}

import Image from "next/image";

import { cn } from "@/lib/utils";

type BrandSize = "sm" | "md" | "lg" | "hero";

/**
 * Wordmark aspect ~2.3:1 — Canva-traced `/brand/koel-logo.svg`.
 * Heights are the optical letter height (tight crop).
 */
const WORDMARK = {
  sm: { width: 92, height: 40, className: "h-5 w-auto" },
  md: { width: 110, height: 48, className: "h-6 w-auto" },
  lg: { width: 147, height: 64, className: "h-8 w-auto" },
  hero: { width: 220, height: 96, className: "h-11 w-auto sm:h-12 md:h-14" },
} as const;

/**
 * Mark is square; in lockups size slightly under the wordmark height so the
 * K optically matches the koel ascenders (not the SVG padding box).
 */
const MARK = {
  sm: { width: 22, height: 22, className: "h-5 w-auto" },
  md: { width: 26, height: 26, className: "h-6 w-auto" },
  lg: { width: 34, height: 34, className: "h-8 w-auto" },
  hero: { width: 52, height: 52, className: "h-11 w-auto sm:h-12 md:h-14" },
} as const;

const LOCKUP_GAP = {
  sm: "gap-2",
  md: "gap-2.5",
  lg: "gap-3",
  hero: "gap-3 sm:gap-3.5",
} as const;

/** Standalone K mark — favicon / compact chrome. */
export function KoelMark({
  size = "md",
  className,
  priority = false,
}: {
  size?: BrandSize;
  className?: string;
  priority?: boolean;
}) {
  const spec = MARK[size];
  return (
    <Image
      src="/brand/koel-mark.svg"
      alt=""
      width={spec.width}
      height={spec.height}
      priority={priority}
      className={cn("shrink-0 object-contain", spec.className, className)}
    />
  );
}

/** Full lowercase wordmark. */
export function KoelWordmark({
  size = "md",
  className,
  priority = false,
}: {
  size?: BrandSize;
  className?: string;
  priority?: boolean;
}) {
  const spec = WORDMARK[size];
  return (
    <Image
      src="/brand/koel-logo.svg"
      alt="koel"
      width={spec.width}
      height={spec.height}
      priority={priority}
      className={cn("object-contain object-left", spec.className, className)}
    />
  );
}

/** Mark + wordmark — branded entry surfaces (login, hero lockups). */
export function KoelLockup({
  size = "lg",
  className,
  priority = false,
}: {
  size?: BrandSize;
  className?: string;
  priority?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center",
        LOCKUP_GAP[size],
        className,
      )}
    >
      <KoelMark size={size} priority={priority} />
      <KoelWordmark size={size} priority={priority} />
    </span>
  );
}

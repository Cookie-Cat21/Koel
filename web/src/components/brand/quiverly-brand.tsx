import Image from "next/image";

import { cn } from "@/lib/utils";

type BrandSize = "sm" | "md" | "lg" | "hero";

/** Aspect ~3.38:1 — matches tight-cropped `/brand/quiverly-logo.svg`. */
const WORDMARK = {
  sm: { width: 108, height: 32, className: "h-6 w-auto" },
  md: { width: 135, height: 40, className: "h-8 w-auto" },
  lg: { width: 183, height: 54, className: "h-10 w-auto" },
  hero: { width: 325, height: 96, className: "h-12 w-auto sm:h-14 md:h-16" },
} as const;

/** Slightly tall Q mark (ring + foot) — matches `/brand/quiverly-mark.svg`. */
const MARK = {
  sm: { width: 26, height: 30, className: "h-7 w-auto" },
  md: { width: 32, height: 36, className: "h-9 w-auto" },
  lg: { width: 42, height: 48, className: "h-12 w-auto" },
  hero: { width: 64, height: 72, className: "h-16 w-auto sm:h-20" },
} as const;

/** Standalone Q mark — favicon / compact chrome. */
export function QuiverlyMark({
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
      src="/brand/quiverly-mark.svg"
      alt=""
      width={spec.width}
      height={spec.height}
      priority={priority}
      className={cn("shrink-0 object-contain", spec.className, className)}
    />
  );
}

/** Full lowercase wordmark from branding/ (tight-cropped for web). */
export function QuiverlyWordmark({
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
      src="/brand/quiverly-logo.svg"
      alt="Quiverly"
      width={spec.width}
      height={spec.height}
      priority={priority}
      className={cn("object-contain object-left", spec.className, className)}
    />
  );
}

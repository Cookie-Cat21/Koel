import Image from "next/image";

import { cn } from "@/lib/utils";

type BrandSize = "sm" | "md" | "lg" | "hero";

/** Aspect ~2.3:1 — matches Canva-traced `/brand/koel-logo.svg`. */
const WORDMARK = {
  sm: { width: 108, height: 48, className: "h-6 w-auto" },
  md: { width: 135, height: 60, className: "h-8 w-auto" },
  lg: { width: 180, height: 80, className: "h-10 w-auto" },
  hero: { width: 288, height: 128, className: "h-12 w-auto sm:h-14 md:h-16" },
} as const;

/** Geometric capital K — matches `/brand/koel-mark.svg`. */
const MARK = {
  sm: { width: 28, height: 28, className: "h-7 w-auto" },
  md: { width: 36, height: 36, className: "h-9 w-auto" },
  lg: { width: 48, height: 48, className: "h-12 w-auto" },
  hero: { width: 72, height: 72, className: "h-16 w-auto sm:h-20" },
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

/** Mark + wordmark lockup — use on branded entry surfaces so the K mark leads. */
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
        "inline-flex items-center gap-3 sm:gap-3.5",
        className,
      )}
    >
      <KoelMark size={size} priority={priority} />
      <KoelWordmark size={size} priority={priority} />
    </span>
  );
}

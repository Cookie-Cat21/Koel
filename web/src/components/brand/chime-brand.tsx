import Image from "next/image";

import { cn } from "@/lib/utils";

type BrandSize = "sm" | "md" | "lg" | "hero";

const WORDMARK = {
  sm: { width: 120, height: 40, className: "h-7 w-auto" },
  md: { width: 160, height: 52, className: "h-8 w-auto" },
  lg: { width: 220, height: 72, className: "h-11 w-auto" },
  hero: { width: 420, height: 140, className: "h-16 w-auto sm:h-20 md:h-24" },
} as const;

const MARK = {
  sm: { width: 28, height: 28, className: "h-7 w-7" },
  md: { width: 36, height: 36, className: "h-9 w-9" },
  lg: { width: 48, height: 48, className: "h-12 w-12" },
  hero: { width: 72, height: 72, className: "h-16 w-16 sm:h-20 sm:w-20" },
} as const;

/** Standalone C mark — favicon / compact chrome (Ceyfi mark pattern). */
export function ChimeMark({
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
      src="/brand/chime-mark.svg"
      alt=""
      width={spec.width}
      height={spec.height}
      priority={priority}
      className={cn("shrink-0 object-contain", spec.className, className)}
    />
  );
}

/** Full lowercase wordmark from branding/ (Dinaya lockup pattern — asset, not CSS text). */
export function ChimeWordmark({
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
      src="/brand/chime-logo.svg"
      alt="Chime"
      width={spec.width}
      height={spec.height}
      priority={priority}
      className={cn("object-contain object-left", spec.className, className)}
    />
  );
}

import type { ComponentProps, ReactNode } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Signal Ice primary CTA — blood red `#E10600` (marketing only). */
export function FiredCtaLink({
  href,
  external,
  children,
  className,
  size = "lg",
}: {
  href: string;
  external?: boolean;
  children: ReactNode;
  className?: string;
  size?: ComponentProps<typeof Button>["size"];
}) {
  return (
    <Button
      asChild
      size={size}
      className={cn(
        "chime-cta-fired min-w-36 border-transparent",
        "motion-safe:transition-transform motion-safe:hover:-translate-y-0.5",
        className,
      )}
    >
      {external ? (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      ) : (
        <Link href={href}>{children}</Link>
      )}
    </Button>
  );
}

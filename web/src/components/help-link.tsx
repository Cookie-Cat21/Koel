import Link from "next/link";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type HelpLinkProps = {
  /** Hash under `/help`, e.g. `alerts` → `/help#alerts`. */
  topic?: string;
  children?: string;
  className?: string;
  /** Outline button (PageHeader actions) vs quiet text link. */
  variant?: "button" | "text";
};

/** Deep-link into the in-app Help center. */
export function HelpLink({
  topic,
  children = "Help",
  className,
  variant = "button",
}: HelpLinkProps) {
  const href =
    typeof topic === "string" && topic
      ? `/help#${topic.replace(/^#/, "")}`
      : "/help";

  if (variant === "text") {
    return (
      <Link
        href={href}
        className={cn(
          "underline underline-offset-4 transition-colors hover:text-foreground",
          className,
        )}
      >
        {children}
      </Link>
    );
  }

  return (
    <Button asChild variant="outline" size="sm" className={className}>
      <Link href={href}>{children}</Link>
    </Button>
  );
}

import { NFA_INLINE } from "@/lib/nfa";
import { cn } from "@/lib/utils";

/** Short NFA line for price-adjacent UI surfaces. */
export function NfaInline({ className }: { className?: string }) {
  return (
    <p className={cn("text-xs text-muted-foreground", className)}>
      {NFA_INLINE}
    </p>
  );
}

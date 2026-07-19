import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** DaisyUI-style chat bubble — Telegram proof on landing (Ceyfi port, koel tokens). */
export function ChatBubble({
  align = "start",
  header,
  footer,
  className,
  children,
}: {
  align?: "start" | "end";
  header?: ReactNode;
  footer?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  const end = align === "end";
  return (
    <div
      className={cn(
        "grid w-full max-w-[min(100%,22rem)] gap-y-1",
        end ? "ml-auto place-items-end" : "mr-auto place-items-start",
        className,
      )}
    >
      {header ? (
        <div className="text-xs font-medium text-muted-foreground">{header}</div>
      ) : null}
      <div
        className={cn(
          "border border-border bg-card px-4 py-3 text-sm leading-relaxed text-foreground shadow-sm",
          end
            ? "rounded-2xl rounded-tr-md"
            : "rounded-2xl rounded-tl-md border-l-4 border-l-foreground",
        )}
      >
        {children}
      </div>
      {footer ? (
        <div className="text-[11px] text-muted-foreground">{footer}</div>
      ) : null}
    </div>
  );
}

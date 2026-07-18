import { cn } from "@/lib/utils";

type InlineErrorProps = {
  message: string | null;
  id?: string;
  className?: string;
};

/**
 * Cap form error copy so a misbuilt caller / hostile API error cannot
 * balloon the alert region (parity with toast / apiErrorMessage).
 */
export const MAX_INLINE_ERROR_LENGTH = 300;

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/g;

/** Strip controls + length-cap before rendering inline error text. */
export function sanitizeInlineError(raw: unknown): string {
  if (typeof raw !== "string") return "Something went wrong.";
  const cleaned = raw.replace(CTRL_RE, "").trim();
  if (!cleaned) return "Something went wrong.";
  return cleaned.length > MAX_INLINE_ERROR_LENGTH
    ? cleaned.slice(0, MAX_INLINE_ERROR_LENGTH).trimEnd()
    : cleaned;
}

/** Form-adjacent validation / API error — accessible, koel destructive tone. */
export function InlineError({ message, id, className }: InlineErrorProps) {
  if (message == null || message === "") return null;
  // Fail closed — never render uncapped / control-laden / non-string errors.
  const safe = sanitizeInlineError(message);
  return (
    <p
      id={id}
      role="alert"
      className={cn(
        "rounded-md border border-destructive/25 bg-destructive/8 px-3 py-2 text-sm text-destructive",
        className,
      )}
    >
      {safe}
    </p>
  );
}

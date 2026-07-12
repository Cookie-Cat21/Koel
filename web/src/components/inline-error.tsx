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
export function sanitizeInlineError(raw: string): string {
  const cleaned = raw.replace(CTRL_RE, "").trim();
  if (!cleaned) return "Something went wrong.";
  return cleaned.length > MAX_INLINE_ERROR_LENGTH
    ? cleaned.slice(0, MAX_INLINE_ERROR_LENGTH).trimEnd()
    : cleaned;
}

/** Form-adjacent validation / API error — accessible, Chime destructive tone. */
export function InlineError({ message, id, className }: InlineErrorProps) {
  if (!message) return null;
  // Fail closed — never render uncapped / control-laden form errors.
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

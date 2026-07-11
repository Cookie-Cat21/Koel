import { cn } from "@/lib/utils";

type InlineErrorProps = {
  message: string | null;
  id?: string;
  className?: string;
};

/** Form-adjacent validation / API error — accessible, Chime destructive tone. */
export function InlineError({ message, id, className }: InlineErrorProps) {
  if (!message) return null;
  return (
    <p
      id={id}
      role="alert"
      className={cn(
        "rounded-md border border-destructive/25 bg-destructive/8 px-3 py-2 text-sm text-destructive",
        className,
      )}
    >
      {message}
    </p>
  );
}

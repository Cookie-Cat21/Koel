export function NfaStrip({ text }: { text?: string }) {
  return (
    <p
      role="note"
      className="rounded-xl border border-ceyfi-line/80 bg-ceyfi-paper/80 px-3 py-2 text-[12px] leading-relaxed text-ceyfi-muted dark:border-white/10 dark:bg-white/[0.04] dark:text-white/55"
    >
      {text ??
        "Information only — not financial advice. Not an invitation to deal in securities. Ceyfi is not a stockbroker."}
    </p>
  );
}

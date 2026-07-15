/**
 * Public marketing CTAs. Bot URL is optional — when unset, Telegram CTA
 * falls back to /login (demo path) so local/dev never 404s.
 */
export function telegramBotUrl(): string | null {
  const raw = process.env.NEXT_PUBLIC_TELEGRAM_BOT_URL;
  if (typeof raw !== "string") return null;
  const trimmed = raw.trim();
  if (!trimmed || trimmed.length > 256) return null;
  if (!/^https:\/\/(t\.me|telegram\.me)\//i.test(trimmed)) return null;
  return trimmed;
}

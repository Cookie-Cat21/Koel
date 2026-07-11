"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NFA_INLINE } from "@/lib/nfa";

type Props = {
  allowlist: number[];
  defaultTelegramId: number | null;
  demoEnabled: boolean;
};

function loginError(message: string) {
  return `${message} ${NFA_INLINE}`;
}

export function LoginForm({ allowlist, defaultTelegramId, demoEnabled }: Props) {
  const router = useRouter();
  const preset =
    defaultTelegramId && allowlist.includes(defaultTelegramId)
      ? String(defaultTelegramId)
      : allowlist.length === 1
        ? String(allowlist[0])
        : "";

  const [telegramId, setTelegramId] = useState(preset);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!demoEnabled) {
    return (
      <p className="text-sm text-muted-foreground">
        Demo sign-in is off. Set <code className="font-mono text-xs">DASH_DEMO_AUTH=1</code>{" "}
        to enable local dashboard access.
      </p>
    );
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const id = Number(telegramId.trim());
      if (!Number.isSafeInteger(id) || id <= 0) {
        setError(loginError("Almost there — enter a valid Telegram ID."));
        return;
      }
      const res = await fetch("/api/v1/auth/demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ telegram_id: id }),
        credentials: "same-origin",
      });
      const data = (await res.json().catch(() => null)) as
        | { error?: { message?: string }; user?: { id: number } }
        | null;
      if (!res.ok) {
        const detail = data?.error?.message
          ? `Chime couldn't sign you in: ${data.error.message}`
          : `Chime couldn't sign you in (${res.status}). Check the allowlisted Telegram ID.`;
        setError(loginError(detail));
        return;
      }
      router.push("/watchlist");
      router.refresh();
    } catch {
      setError(loginError("Chime couldn't reach the sign-in endpoint. Try again."));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex w-full max-w-sm flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="telegram_id">Demo Telegram ID</Label>
        {allowlist.length > 1 ? (
          <select
            id="telegram_id"
            className="border-input bg-background h-9 rounded-lg border px-3 text-sm"
            value={telegramId}
            onChange={(e) => setTelegramId(e.target.value)}
            required
          >
            <option value="" disabled>
              Select allowlisted ID
            </option>
            {allowlist.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        ) : (
          <Input
            id="telegram_id"
            name="telegram_id"
            inputMode="numeric"
            autoComplete="off"
            placeholder="123456789"
            value={telegramId}
            onChange={(e) => setTelegramId(e.target.value)}
            required
          />
        )}
        <p className="text-xs text-muted-foreground">
          Must be in <code className="font-mono">DASH_DEMO_TELEGRAM_IDS</code>. Not
          financial advice.
        </p>
      </div>
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <Button type="submit" disabled={pending} size="lg">
        {pending ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}

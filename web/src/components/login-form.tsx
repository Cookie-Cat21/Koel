"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { InlineError } from "@/components/inline-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  apiErrorMessage,
  CLIENT_API_BODY_MAX_CHARS,
  CLIENT_API_TIMEOUT_MS,
} from "@/lib/api/client-fetch";
import { readBoundedResponseText } from "@/lib/api/read-bounded-text";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import { NFA_INLINE } from "@/lib/nfa";

type Props = {
  /** Only populated when DASH_DEMO_SHOW_ALLOWLIST=1 (S-11). */
  allowlist: number[];
  defaultTelegramId: number | null;
  demoEnabled: boolean;
};

function loginError(message: string) {
  return `${message} ${NFA_INLINE}`;
}

export function LoginForm({ allowlist, defaultTelegramId, demoEnabled }: Props) {
  const router = useRouter();
  const reactId = useId();
  const fieldId = `telegram_id-${reactId}`;
  const helpId = `telegram_id_help-${reactId}`;
  const errorId = `telegram_id_error-${reactId}`;
  // Prefer explicit default; allowlist select only when SHOW_ALLOWLIST=1 (S-11).
  const preset =
    defaultTelegramId != null
      ? String(defaultTelegramId)
      : allowlist.length === 1
        ? String(allowlist[0])
        : "";

  const [telegramId, setTelegramId] = useState(preset);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!demoEnabled) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
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
      const id = toSafePositiveInt(telegramId.trim());
      if (id == null) {
        setError(loginError("Almost there — enter a valid Telegram ID."));
        return;
      }
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), CLIENT_API_TIMEOUT_MS);
      let res: Response;
      try {
        res = await fetch("/api/v1/auth/demo", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ telegram_id: id }),
          credentials: "same-origin",
          signal: ctrl.signal,
        });
      } finally {
        clearTimeout(timer);
      }
      // Stream-bound body — missing / understated Content-Length must not
      // let res.text() allocate past the cap.
      const bounded = await readBoundedResponseText(
        res,
        CLIENT_API_BODY_MAX_CHARS,
      );
      if (!bounded.ok) {
        setError(
          loginError(
            "Chime couldn't sign you in (response too large). Try again.",
          ),
        );
        return;
      }
      let data: unknown = null;
      try {
        data = bounded.text ? JSON.parse(bounded.text) : null;
      } catch {
        data = null;
      }
      if (!res.ok) {
        // Uniform denial copy — do not echo allowlist membership (S-11).
        const code =
          data && typeof data === "object" && !Array.isArray(data)
            ? (data as { error?: { code?: unknown } }).error?.code
            : null;
        if (
          code === "demo_auth_denied" ||
          code === "telegram_id_not_allowlisted"
        ) {
          setError(
            loginError(
              "Chime couldn't sign you in. Check the Telegram ID and try again.",
            ),
          );
          return;
        }
        // Cap + strip controls — hostile error.message must not balloon UI.
        const apiMsg = apiErrorMessage(data, "");
        const detail = apiMsg
          ? `Chime couldn't sign you in: ${apiMsg}`
          : `Chime couldn't sign you in (${res.status}). Try again.`;
        setError(loginError(detail));
        return;
      }
      router.push("/overview");
      router.refresh();
    } catch {
      setError(loginError("Chime couldn't reach the sign-in endpoint. Try again."));
    } finally {
      setPending(false);
    }
  }

  const describedBy = error ? `${helpId} ${errorId}` : helpId;

  return (
    <form
      onSubmit={onSubmit}
      method="post"
      action="/api/v1/auth/demo"
      className="flex w-full max-w-sm flex-col gap-4"
      aria-labelledby="login-sign-in-heading"
      noValidate
    >
      <h2 id="login-sign-in-heading" className="sr-only">
        Sign in
      </h2>
      <div className="flex flex-col gap-2">
        <Label htmlFor={fieldId}>Demo Telegram ID</Label>
        {allowlist.length > 1 ? (
          <select
            id={fieldId}
            name="telegram_id"
            className="border-input bg-background h-9 rounded-lg border px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20"
            value={telegramId}
            onChange={(e) => {
              setTelegramId(e.target.value);
              if (error) setError(null);
            }}
            required
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
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
            id={fieldId}
            name="telegram_id"
            inputMode="numeric"
            autoComplete="username"
            placeholder="123456789"
            value={telegramId}
            onChange={(e) => {
              setTelegramId(e.target.value);
              if (error) setError(null);
            }}
            required
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
          />
        )}
        <p id={helpId} className="text-xs text-muted-foreground">
          Demo sign-in for allowlisted Telegram IDs only. Not financial advice.
        </p>
      </div>
      <InlineError id={errorId} message={error} />
      <Button
        type="submit"
        disabled={pending}
        size="lg"
        aria-busy={pending || undefined}
      >
        {pending ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}

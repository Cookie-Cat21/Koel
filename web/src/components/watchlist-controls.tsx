"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { InlineError } from "@/components/inline-error";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiErrorMessage, apiMutate } from "@/lib/api/client-fetch";

export function WatchlistAddForm() {
  const router = useRouter();
  const toast = useToast();
  const [symbol, setSymbol] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const trimmed = symbol.trim().toUpperCase();
      if (!trimmed) {
        setError("Enter a CSE symbol.");
        return;
      }
      const { ok, status, data } = await apiMutate("/api/v1/watchlist", {
        method: "POST",
        body: { symbol: trimmed },
      });
      if (!ok) {
        const msg = apiErrorMessage(data, `Could not add (${status}).`);
        setError(msg);
        toast.error(msg);
        return;
      }
      setSymbol("");
      toast.success(`Watching ${trimmed}. Pushes still go to Telegram.`);
      router.refresh();
    } catch {
      const msg = "Network error. Try again.";
      setError(msg);
      toast.error(msg);
    } finally {
      setPending(false);
    }
  }

  return (
    <form
      id="watchlist-add"
      onSubmit={onSubmit}
      className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end"
      noValidate
    >
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <Label htmlFor="watch_symbol">Add symbol</Label>
        <Input
          id="watch_symbol"
          name="symbol"
          className="h-10 font-mono"
          placeholder="e.g. JKH.N0000"
          value={symbol}
          onChange={(e) => {
            setSymbol(e.target.value);
            if (error) setError(null);
          }}
          autoComplete="off"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "watch_symbol_error" : undefined}
          required
        />
      </div>
      <Button type="submit" disabled={pending} className="h-10 shrink-0">
        {pending ? "Adding…" : "Add"}
      </Button>
      <InlineError
        id="watch_symbol_error"
        message={error}
        className="w-full sm:basis-full"
      />
    </form>
  );
}

export function UnwatchButton({ symbol }: { symbol: string }) {
  const router = useRouter();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onClick() {
    setError(null);
    setPending(true);
    try {
      const { ok, status, data } = await apiMutate(
        `/api/v1/watchlist/${encodeURIComponent(symbol)}`,
        { method: "DELETE" },
      );
      if (!ok) {
        const msg = apiErrorMessage(data, `Could not unwatch (${status}).`);
        setError(msg);
        toast.error(msg);
        return;
      }
      toast.success(`Removed ${symbol} from watchlist.`);
      router.refresh();
    } catch {
      const msg = "Network error.";
      setError(msg);
      toast.error(msg);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={pending}
        onClick={onClick}
      >
        {pending ? "…" : "Unwatch"}
      </Button>
      <InlineError
        message={error}
        className="max-w-[12rem] px-2 py-1 text-right text-xs"
      />
    </div>
  );
}

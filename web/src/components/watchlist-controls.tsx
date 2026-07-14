"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { InlineError } from "@/components/inline-error";
import { useToast } from "@/components/toast";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiErrorMessage, apiMutate } from "@/lib/api/client-fetch";
import { normalizeSymbol } from "@/lib/api/symbol";

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
      const normalized = normalizeSymbol(symbol);
      if (!normalized) {
        setError("Enter a CSE symbol (e.g. JKH.N0000).");
        return;
      }
      const { ok, status, data } = await apiMutate("/api/v1/watchlist", {
        method: "POST",
        body: { symbol: normalized },
      });
      if (!ok) {
        const msg = apiErrorMessage(data, `Could not add (${status}).`);
        setError(msg);
        toast.error(msg);
        return;
      }
      setSymbol("");
      // Soft duplicate messaging: body.created (or 200) means already watching.
      const created =
        data &&
        typeof data === "object" &&
        "created" in data &&
        typeof (data as { created: unknown }).created === "boolean"
          ? (data as { created: boolean }).created
          : status === 201;
      toast.success(
        created
          ? `Watching ${normalized}. Pushes still go to Telegram.`
          : `Already watching ${normalized}. Pushes still go to Telegram.`,
      );
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

/** Watch or Unwatch CTA — pass ``watching`` from SSR watchlist membership. */
export function WatchButton({
  symbol,
  watching = false,
}: {
  symbol: string;
  watching?: boolean;
}) {
  if (watching) return <UnwatchButton symbol={symbol} />;
  return <WatchAddButton symbol={symbol} />;
}

function WatchAddButton({ symbol }: { symbol: string }) {
  const router = useRouter();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onClick() {
    setError(null);
    // Fail closed — hostile / non-SYMBOL_RE props must not hit POST.
    const normalized = normalizeSymbol(symbol);
    if (!normalized) {
      const msg = "Invalid CSE symbol.";
      setError(msg);
      toast.error(msg);
      return;
    }
    setPending(true);
    try {
      const { ok, status, data } = await apiMutate("/api/v1/watchlist", {
        method: "POST",
        body: { symbol: normalized },
      });
      if (!ok) {
        const msg = apiErrorMessage(data, `Could not watch (${status}).`);
        setError(msg);
        toast.error(msg);
        return;
      }
      const created =
        data &&
        typeof data === "object" &&
        "created" in data &&
        typeof (data as { created: unknown }).created === "boolean"
          ? (data as { created: boolean }).created
          : status === 201;
      toast.success(
        created
          ? `Watching ${normalized}. Pushes still go to Telegram.`
          : `Already watching ${normalized}. Pushes still go to Telegram.`,
      );
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
        size="sm"
        disabled={pending}
        onClick={onClick}
        aria-busy={pending || undefined}
      >
        {pending ? "…" : "Watch"}
      </Button>
      <InlineError
        message={error}
        className="max-w-[12rem] px-2 py-1 text-right text-xs"
      />
    </div>
  );
}

export function UnwatchButton({ symbol }: { symbol: string }) {
  const router = useRouter();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [open, setOpen] = useState(false);

  async function confirmUnwatch() {
    setError(null);
    // Fail closed — hostile / non-SYMBOL_RE props must not hit DELETE.
    const normalized = normalizeSymbol(symbol);
    if (!normalized) {
      const msg = "Invalid CSE symbol.";
      setError(msg);
      toast.error(msg);
      return;
    }
    setPending(true);
    try {
      const { ok, status, data } = await apiMutate(
        `/api/v1/watchlist/${encodeURIComponent(normalized)}`,
        { method: "DELETE" },
      );
      if (!ok) {
        const msg = apiErrorMessage(data, `Could not unwatch (${status}).`);
        setError(msg);
        toast.error(msg);
        return;
      }
      toast.success(`Removed ${normalized}. Telegram pushes for it are off.`);
      setOpen(false);
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
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogTrigger asChild>
          <Button type="button" variant="outline" size="sm" disabled={pending}>
            Unwatch
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unwatch {symbol}?</AlertDialogTitle>
            <AlertDialogDescription>
              Removes it from your watchlist and deactivates related alerts.
              Telegram pushes for this symbol stop.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending}>Keep</AlertDialogCancel>
            <AlertDialogAction
              disabled={pending}
              onClick={(e) => {
                e.preventDefault();
                void confirmUnwatch();
              }}
            >
              {pending ? "…" : "Unwatch"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <InlineError
        message={error}
        className="max-w-[12rem] px-2 py-1 text-right text-xs"
      />
    </div>
  );
}

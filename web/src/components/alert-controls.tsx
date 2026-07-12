"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { InlineError } from "@/components/inline-error";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiErrorMessage, apiMutate } from "@/lib/api/client-fetch";
import { ALERT_TYPES, type AlertType } from "@/lib/api/symbol";

const TYPE_OPTIONS: { value: AlertType; label: string }[] = [
  { value: "price_above", label: "Above price" },
  { value: "price_below", label: "Below price" },
  { value: "daily_move", label: "Daily move %" },
  { value: "disclosure", label: "New disclosure" },
];

type FieldErrors = {
  symbol?: string;
  type?: string;
  threshold?: string;
  category?: string;
  form?: string;
};

export function AlertCreateForm() {
  const router = useRouter();
  const toast = useToast();
  const [symbol, setSymbol] = useState("");
  const [type, setType] = useState<AlertType>("price_above");
  const [threshold, setThreshold] = useState("");
  const [category, setCategory] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [pending, setPending] = useState(false);

  const needsThreshold = type !== "disclosure";
  const showCategory = type === "disclosure";

  function clearField(key: keyof FieldErrors) {
    setErrors((prev) => {
      if (!prev[key] && !prev.form) return prev;
      const next = { ...prev };
      delete next[key];
      delete next.form;
      return next;
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});
    setPending(true);
    try {
      const next: FieldErrors = {};
      const trimmed = symbol.trim().toUpperCase();
      if (!trimmed) {
        next.symbol = "Enter a CSE symbol (e.g. JKH.N0000).";
      }
      if (!ALERT_TYPES.includes(type)) {
        next.type = "Pick a valid alert type.";
      }

      const body: {
        symbol: string;
        type: AlertType;
        threshold?: number;
        category?: string;
      } = { symbol: trimmed, type };

      if (needsThreshold) {
        const raw = threshold.trim();
        if (!raw) {
          next.threshold =
            type === "daily_move"
              ? "Enter a percent move (e.g. 5)."
              : "Enter a price threshold.";
        } else {
          const n = Number(raw);
          if (!Number.isFinite(n)) {
            next.threshold = "Threshold must be a number.";
          } else if (type === "daily_move" && n <= 0) {
            next.threshold = "Daily move percent must be greater than zero.";
          } else if (
            (type === "price_above" || type === "price_below") &&
            n <= 0
          ) {
            next.threshold = "Price threshold must be greater than zero.";
          } else {
            body.threshold = n;
          }
        }
      } else {
        const cat = category.trim();
        if (cat) {
          body.category = cat;
        }
      }

      if (Object.keys(next).length > 0) {
        setErrors(next);
        return;
      }

      const { ok, status, data } = await apiMutate("/api/v1/alerts", {
        method: "POST",
        body,
      });
      if (!ok) {
        const msg = apiErrorMessage(data, `Could not create (${status}).`);
        // Map common API codes to fields when possible
        const code =
          data &&
          typeof data === "object" &&
          "error" in data &&
          data.error &&
          typeof data.error === "object" &&
          "code" in data.error
            ? String((data.error as { code?: string }).code ?? "")
            : "";
        if (code === "invalid_symbol" || code === "not_found") {
          setErrors({ symbol: msg });
        } else if (msg.toLowerCase().includes("threshold")) {
          setErrors({ threshold: msg });
        } else if (msg.toLowerCase().includes("category")) {
          setErrors({ category: msg });
        } else if (msg.toLowerCase().includes("type")) {
          setErrors({ type: msg });
        } else {
          setErrors({ form: msg });
        }
        toast.error(msg);
        return;
      }
      setSymbol("");
      setThreshold("");
      setCategory("");
      toast.success(
        `Alert set for ${trimmed}. Telegram will ping when it fires.`,
      );
      router.refresh();
    } catch {
      const msg = "Network error. Try again.";
      setErrors({ form: msg });
      toast.error(msg);
    } finally {
      setPending(false);
    }
  }

  const formError =
    errors.form ??
    errors.symbol ??
    errors.type ??
    errors.threshold ??
    errors.category ??
    null;

  return (
    <form
      onSubmit={onSubmit}
      className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
      noValidate
    >
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="alert_symbol">Symbol</Label>
        <Input
          id="alert_symbol"
          name="symbol"
          className="h-10 font-mono"
          placeholder="JKH.N0000"
          value={symbol}
          onChange={(e) => {
            setSymbol(e.target.value);
            clearField("symbol");
          }}
          autoComplete="off"
          aria-invalid={errors.symbol ? true : undefined}
          aria-describedby={errors.symbol ? "alert_form_error" : undefined}
          required
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="alert_type">Type</Label>
        <select
          id="alert_type"
          className="border-input bg-background h-10 rounded-lg border px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
          value={type}
          onChange={(e) => {
            const nextType = e.target.value as AlertType;
            setType(nextType);
            if (nextType === "disclosure") {
              setThreshold("");
            } else {
              setCategory("");
            }
            clearField("type");
            clearField("threshold");
            clearField("category");
          }}
          aria-invalid={errors.type ? true : undefined}
        >
          {TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      {needsThreshold ? (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="alert_threshold">
            {type === "daily_move" ? "Percent" : "Price"}
          </Label>
          <Input
            id="alert_threshold"
            name="threshold"
            className="h-10 font-mono"
            inputMode="decimal"
            placeholder={type === "daily_move" ? "5" : "25.00"}
            value={threshold}
            onChange={(e) => {
              setThreshold(e.target.value);
              clearField("threshold");
            }}
            aria-invalid={errors.threshold ? true : undefined}
            aria-describedby={
              errors.threshold ? "alert_form_error" : undefined
            }
            required
          />
        </div>
      ) : showCategory ? (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="alert_category">Category (optional)</Label>
          <Input
            id="alert_category"
            name="category"
            className="h-10"
            placeholder="e.g. Financial Report"
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              clearField("category");
            }}
            autoComplete="off"
            aria-invalid={errors.category ? true : undefined}
            aria-describedby={
              errors.category ? "alert_form_error" : "alert_category_hint"
            }
          />
          <p id="alert_category_hint" className="text-xs text-muted-foreground">
            Leave blank for any filing; substring match when set.
          </p>
        </div>
      ) : (
        <div className="hidden lg:block" aria-hidden />
      )}
      <div className="flex flex-col justify-end gap-1.5">
        <Button type="submit" disabled={pending} className="h-10 w-full sm:w-auto">
          {pending ? "Creating…" : "Create alert"}
        </Button>
      </div>
      <InlineError
        id="alert_form_error"
        message={formError}
        className="sm:col-span-2 lg:col-span-4"
      />
    </form>
  );
}

export function CancelAlertButton({ ruleId }: { ruleId: number }) {
  const router = useRouter();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onClick() {
    setError(null);
    setPending(true);
    try {
      const { ok, status, data } = await apiMutate(`/api/v1/alerts/${ruleId}`, {
        method: "DELETE",
      });
      if (!ok) {
        const msg = apiErrorMessage(data, `Could not cancel (${status}).`);
        setError(msg);
        toast.error(msg);
        return;
      }
      toast.success(`Cancelled alert #${ruleId}.`);
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
        {pending ? "…" : "Cancel"}
      </Button>
      <InlineError
        message={error}
        className="max-w-[12rem] px-2 py-1 text-right text-xs"
      />
    </div>
  );
}

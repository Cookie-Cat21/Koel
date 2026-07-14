"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { InlineError } from "@/components/inline-error";
import { useToast } from "@/components/toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiErrorMessage, apiMutate } from "@/lib/api/client-fetch";
import {
  DISCLOSURE_CATEGORY_MAX,
  sanitizeDisclosureCategory,
} from "@/lib/api/disclosure-safe";
import {
  MAX_ALERT_THRESHOLD,
  toFiniteNumber,
} from "@/lib/api/finite-number";
import { toSafePositiveInt } from "@/lib/api/safe-int";
import {
  ALERT_TYPES,
  NOTICE_ALERT_TYPES,
  type AlertType,
  isAlertType,
  normalizeSymbol,
} from "@/lib/api/symbol";

const TYPE_OPTIONS: { value: AlertType; label: string }[] = [
  { value: "price_above", label: "Above price" },
  { value: "price_below", label: "Below price" },
  { value: "daily_move", label: "Daily move %" },
  { value: "disclosure", label: "New disclosure" },
  { value: "volume_spike", label: "Volume spike (× avg)" },
  { value: "volume_up", label: "Heavy volume + up" },
  { value: "volume_down", label: "Heavy volume + down" },
  { value: "crossing_volume", label: "Crossing volume (×)" },
  { value: "big_print", label: "Big print (shares)" },
  { value: "gap", label: "Open gap %" },
  { value: "buy_in", label: "Buy-in board" },
  { value: "non_compliance", label: "Non-compliance" },
  { value: "halt", label: "Market halt (MARKET)" },
  { value: "bid_heavy", label: "Bid-heavy book (×)" },
  { value: "ask_heavy", label: "Ask-heavy book (×)" },
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

  const needsThreshold = !(NOTICE_ALERT_TYPES as readonly string[]).includes(type);
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
      const normalized = normalizeSymbol(symbol);
      if (!normalized) {
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
      } = { symbol: normalized ?? "", type };

      if (needsThreshold) {
        const raw = threshold.trim();
        if (!raw) {
          next.threshold =
            type === "daily_move"
              ? "Enter a percent move (e.g. 5)."
              : "Enter a price threshold.";
        } else {
          // Decimal-only via toFiniteNumber — Number("1e2") / Number("")→0
          // used to soft-accept sci-notation and empty thresholds.
          const n = toFiniteNumber(raw);
          if (n == null) {
            next.threshold = "Threshold must be a number.";
          } else if (n <= 0) {
            next.threshold =
              type === "daily_move" || type === "gap"
                ? "Percent threshold must be greater than zero."
                : type === "big_print"
                  ? "Share quantity must be greater than zero."
                  : type.startsWith("volume") || type === "crossing_volume"
                    ? "Multiplier must be greater than zero."
                    : "Threshold must be greater than zero.";
          } else if (n > MAX_ALERT_THRESHOLD) {
            next.threshold = "Threshold is too large.";
          } else {
            body.threshold = n;
          }
        }
      } else {
        const cat = sanitizeDisclosureCategory(category);
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
        const codeRaw =
          data &&
          typeof data === "object" &&
          "error" in data &&
          data.error &&
          typeof data.error === "object" &&
          "code" in data.error
            ? (data.error as { code?: unknown }).code
            : undefined;
        // Fail closed — never String()-coerce non-string error codes (objects
        // used to become "[object Object]" and mis-route field errors).
        const code = typeof codeRaw === "string" ? codeRaw : "";
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
        `Alert set for ${normalized}. Telegram will ping when it fires.`,
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
        <Select
          value={type}
          onValueChange={(value) => {
            // Fail closed — tampered Select values must not cast into state.
            if (!isAlertType(value)) return;
            const nextType = value;
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
        >
          <SelectTrigger
            id="alert_type"
            className="h-10 w-full"
            aria-invalid={errors.type ? true : undefined}
          >
            <SelectValue placeholder="Alert type" />
          </SelectTrigger>
          <SelectContent>
            {TYPE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
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
            maxLength={DISCLOSURE_CATEGORY_MAX}
            aria-invalid={errors.category ? true : undefined}
            aria-describedby={
              errors.category
                ? "alert_category_hint alert_form_error"
                : "alert_category_hint"
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
        <Button
          type="submit"
          disabled={pending}
          className="h-10 w-full sm:w-auto"
          aria-busy={pending || undefined}
        >
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
    // Fail closed — NaN / float / ≤0 must not hit DELETE /alerts/{id}.
    const id = toSafePositiveInt(ruleId);
    if (id == null) {
      const msg = "Invalid alert id.";
      setError(msg);
      toast.error(msg);
      return;
    }
    setPending(true);
    try {
      const { ok, status, data } = await apiMutate(`/api/v1/alerts/${id}`, {
        method: "DELETE",
      });
      if (!ok) {
        const msg = apiErrorMessage(data, `Could not cancel (${status}).`);
        setError(msg);
        toast.error(msg);
        return;
      }
      toast.success(`Cancelled alert #${id}.`);
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

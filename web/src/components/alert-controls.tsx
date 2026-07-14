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
import { Separator } from "@/components/ui/separator";
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
  type AlertType,
  isAlertType,
  isFilingMetricsAlertType,
  isThresholdAlertType,
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
  { value: "eps_above", label: "EPS above" },
  { value: "eps_below", label: "EPS below" },
  { value: "eps_yoy_above", label: "EPS YoY above" },
  { value: "eps_yoy_below", label: "EPS YoY below" },
  { value: "rev_yoy_above", label: "Revenue YoY above" },
  { value: "rev_yoy_below", label: "Revenue YoY below" },
  { value: "profit_yoy_above", label: "Profit YoY above" },
  { value: "profit_yoy_below", label: "Profit YoY below" },
];

const MUTE_MS = 24 * 60 * 60 * 1000;

type FieldErrors = {
  symbol?: string;
  type?: string;
  threshold?: string;
  category?: string;
  form?: string;
};

export function AlertCreateForm({
  initialSymbol = "",
  initialType,
}: {
  initialSymbol?: string;
  /** Prefill from ``/alerts?type=disclosure`` (and friends). */
  initialType?: AlertType | null;
} = {}) {
  const router = useRouter();
  const toast = useToast();
  const [symbol, setSymbol] = useState(() => normalizeSymbol(initialSymbol) ?? "");
  const [type, setType] = useState<AlertType>(() =>
    initialType && ALERT_TYPES.includes(initialType) ? initialType : "price_above",
  );
  const [threshold, setThreshold] = useState("");
  const [category, setCategory] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [pending, setPending] = useState(false);

  const needsThreshold = isThresholdAlertType(type);
  const showCategory = type === "disclosure";
  const showFilingMetricsNote = isFilingMetricsAlertType(type);
  const thresholdLabel = thresholdFieldLabel(type);
  const thresholdPlaceholder = thresholdFieldPlaceholder(type);

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
      let normalized = normalizeSymbol(symbol);
      if (type === "halt") {
        normalized = "MARKET";
        setSymbol("MARKET");
      }
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
            thresholdLabel === "Percent"
              ? "Enter a percent threshold (e.g. 5)."
              : `Enter a ${thresholdLabel.toLowerCase()} threshold.`;
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
                  : thresholdLabel === "Multiplier"
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
      className="mt-6 rounded-lg border border-border/70 p-4 sm:p-5"
      noValidate
    >
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_auto_minmax(0,1fr)_auto_minmax(12rem,auto)] lg:items-start">
        <section
          aria-labelledby="alert-symbol-type-heading"
          className="flex flex-col gap-3"
        >
          <h3
            id="alert-symbol-type-heading"
            className="text-xs font-medium tracking-wide text-muted-foreground uppercase"
          >
            Symbol & type
          </h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
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
                  if (nextType === "halt") {
                    setSymbol("MARKET");
                    clearField("symbol");
                  }
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
          </div>
        </section>

        <Separator className="lg:hidden" />
        <Separator orientation="vertical" className="hidden lg:block" />

        <section
          aria-labelledby="alert-threshold-category-heading"
          className="flex flex-col gap-3"
        >
          <h3
            id="alert-threshold-category-heading"
            className="text-xs font-medium tracking-wide text-muted-foreground uppercase"
          >
            Threshold / category
          </h3>
          {needsThreshold ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="alert_threshold">{thresholdLabel}</Label>
              <Input
                id="alert_threshold"
                name="threshold"
                className="h-10 font-mono"
                inputMode="decimal"
                placeholder={thresholdPlaceholder}
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
            <p className="text-sm text-muted-foreground">
              This notice rule does not need a threshold.
            </p>
          )}
        </section>

        <Separator className="lg:hidden" />
        <Separator orientation="vertical" className="hidden lg:block" />

        <section
          aria-labelledby="alert-submit-heading"
          className="flex flex-col gap-3"
        >
          <h3
            id="alert-submit-heading"
            className="text-xs font-medium tracking-wide text-muted-foreground uppercase"
          >
            Submit
          </h3>
          <Button
            type="submit"
            disabled={pending}
            className="h-10 w-full"
            aria-busy={pending || undefined}
          >
            {pending ? "Creating…" : "Create alert"}
          </Button>
          <InlineError id="alert_form_error" message={formError} />
        </section>
      </div>
      {showFilingMetricsNote ? (
        <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
          Fires when financial metrics extract + flags are on (FINANCIAL_METRICS
          / YOY_COMPARE). Shadow mode may log without Telegram.
        </p>
      ) : null}
    </form>
  );
}

function thresholdFieldLabel(type: AlertType): string {
  if (type === "daily_move" || type === "gap" || type.includes("_yoy_")) {
    return "Percent";
  }
  if (type === "big_print") return "Shares";
  if (
    type.startsWith("volume") ||
    type === "crossing_volume" ||
    type === "bid_heavy" ||
    type === "ask_heavy"
  ) {
    return "Multiplier";
  }
  if (type === "eps_above" || type === "eps_below") return "EPS";
  return "Price";
}

function thresholdFieldPlaceholder(type: AlertType): string {
  if (type === "daily_move" || type === "gap" || type.includes("_yoy_")) {
    return "5";
  }
  if (type === "big_print") return "10000";
  if (
    type.startsWith("volume") ||
    type === "crossing_volume" ||
    type === "bid_heavy" ||
    type === "ask_heavy"
  ) {
    return "2";
  }
  if (type === "eps_above" || type === "eps_below") return "1.25";
  return "25.00";
}

export function CancelAlertButton({ ruleId }: { ruleId: number }) {
  const router = useRouter();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [open, setOpen] = useState(false);

  async function confirmCancel() {
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
            Cancel
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel alert #{ruleId}?</AlertDialogTitle>
            <AlertDialogDescription>
              Deactivates this rule. Telegram will no longer fire for it. You
              can create a new rule anytime.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pending}>Keep</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={pending}
              onClick={(e) => {
                e.preventDefault();
                void confirmCancel();
              }}
            >
              {pending ? "Cancelling…" : "Cancel alert"}
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

export function MuteAlertButton({
  ruleId,
  mutedUntil,
}: {
  ruleId: number;
  mutedUntil?: string | null;
}) {
  const router = useRouter();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  // Snapshot once per mount — purity rule; refresh remounts after mute PATCH.
  const [nowMs] = useState(() => Date.now());
  const mutedMs =
    typeof mutedUntil === "string" && mutedUntil
      ? Date.parse(mutedUntil)
      : Number.NaN;
  const isMuted = Number.isFinite(mutedMs) && mutedMs > nowMs;

  async function onClick() {
    setError(null);
    const id = toSafePositiveInt(ruleId);
    if (id == null) {
      const msg = "Invalid alert id.";
      setError(msg);
      toast.error(msg);
      return;
    }
    const muted_until = isMuted
      ? null
      : new Date(Date.now() + MUTE_MS).toISOString();
    setPending(true);
    try {
      const { ok, status, data } = await apiMutate(`/api/v1/alerts/${id}`, {
        method: "PATCH",
        body: { muted_until },
      });
      if (!ok) {
        const msg = apiErrorMessage(data, `Could not update mute (${status}).`);
        setError(msg);
        toast.error(msg);
        return;
      }
      toast.success(
        muted_until
          ? `Muted alert #${id} for 24 hours.`
          : `Cleared mute for alert #${id}.`,
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
        variant={isMuted ? "outline" : "ghost"}
        size="sm"
        disabled={pending}
        onClick={() => void onClick()}
        aria-busy={pending || undefined}
      >
        {pending ? "…" : isMuted ? "Clear mute" : "Mute 24h"}
      </Button>
      <InlineError
        message={error}
        className="max-w-[12rem] px-2 py-1 text-right text-xs"
      />
    </div>
  );
}

/** Ops dry-run — writes audit row; does not send Telegram (C2). */
export function TestFireButton({ ruleId }: { ruleId: number }) {
  const router = useRouter();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onClick() {
    setError(null);
    const id = toSafePositiveInt(ruleId);
    if (id == null) {
      const msg = "Invalid alert id.";
      setError(msg);
      toast.error(msg);
      return;
    }
    setPending(true);
    try {
      const { ok, status, data } = await apiMutate(
        `/api/v1/alerts/${id}/test-fire`,
        { method: "POST", body: {} },
      );
      if (!ok) {
        const msg = apiErrorMessage(data, `Test fire failed (${status}).`);
        setError(msg);
        toast.error(msg);
        return;
      }
      toast.success(`Dry-run logged for alert #${id} — no Telegram send.`);
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
        variant="ghost"
        size="sm"
        disabled={pending}
        onClick={() => void onClick()}
        aria-busy={pending || undefined}
      >
        {pending ? "…" : "Test fire"}
      </Button>
      <InlineError
        message={error}
        className="max-w-[12rem] px-2 py-1 text-right text-xs"
      />
    </div>
  );
}

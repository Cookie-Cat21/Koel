"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

export type ToastTone = "error" | "success" | "info";

const TOAST_TONES = new Set<ToastTone>(["error", "success", "info"]);

type ToastItem = {
  id: string;
  message: string;
  tone: ToastTone;
};

type ToastApi = {
  push: (message: string, tone?: ToastTone) => void;
  error: (message: string) => void;
  success: (message: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

const AUTO_DISMISS_MS = 4500;

/** Max concurrent toasts — overflow must dismiss (clear timers), not leak. */
export const MAX_VISIBLE_TOASTS = 3;

/**
 * Cap toast copy so a misbuilt caller / hostile API error cannot balloon
 * the live region (parity with ``MAX_API_ERROR_MESSAGE_LENGTH``).
 */
export const MAX_TOAST_MESSAGE_LENGTH = 300;

const CTRL_RE = /[\u0000-\u001F\u007F-\u009F]/g;

/** Fail-closed tone — unknown / hostile values must not reach className. */
export function normalizeToastTone(raw: unknown): ToastTone {
  return typeof raw === "string" && TOAST_TONES.has(raw as ToastTone)
    ? (raw as ToastTone)
    : "info";
}

/** Strip controls + length-cap before rendering toast text. */
export function sanitizeToastMessage(raw: unknown): string {
  // Fail closed — non-strings used to throw on .replace (parity InlineError).
  if (typeof raw !== "string") return "Something went wrong.";
  const cleaned = raw.replace(CTRL_RE, "").trim();
  if (!cleaned) return "Something went wrong.";
  return cleaned.length > MAX_TOAST_MESSAGE_LENGTH
    ? cleaned.slice(0, MAX_TOAST_MESSAGE_LENGTH).trimEnd()
    : cleaned;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: string) => {
    const t = timers.current.get(id);
    if (t) {
      clearTimeout(t);
      timers.current.delete(id);
    }
    setItems((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (message: string, tone: ToastTone = "info") => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      // Fail closed — never render uncapped / control-laden / non-string toast copy.
      const safe = sanitizeToastMessage(message);
      const safeTone = normalizeToastTone(tone);
      setItems((prev) => {
        const next = [...prev, { id, message: safe, tone: safeTone }];
        // Overflow must clear timers — slice-only used to leak dismiss timers.
        while (next.length > MAX_VISIBLE_TOASTS) {
          const dropped = next.shift();
          if (!dropped) break;
          const t = timers.current.get(dropped.id);
          if (t) {
            clearTimeout(t);
            timers.current.delete(dropped.id);
          }
        }
        return next;
      });
      const t = setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
      timers.current.set(id, t);
    },
    [dismiss],
  );

  useEffect(() => {
    const map = timers.current;
    return () => {
      for (const t of map.values()) clearTimeout(t);
      map.clear();
    };
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      push,
      error: (message) => push(message, "error"),
      success: (message) => push(message, "success"),
    }),
    [push],
  );

  const regionId = useId();

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        id={regionId}
        aria-live="polite"
        aria-relevant="additions"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4 sm:items-end sm:p-6"
      >
        {items.map((item) => (
          <div
            key={item.id}
            role={item.tone === "error" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto koel-rise w-full max-w-sm rounded-lg border px-4 py-3 text-sm shadow-sm backdrop-blur-sm",
              item.tone === "error" &&
                "border-destructive/30 bg-background/95 text-destructive",
              item.tone === "success" &&
                "border-[oklch(0.55_0.08_165)]/35 bg-background/95 text-[oklch(0.36_0.06_165)]",
              item.tone === "info" &&
                "border-border/80 bg-background/95 text-foreground",
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <p className="min-w-0 leading-snug">{item.message}</p>
              <button
                type="button"
                className="shrink-0 text-xs text-muted-foreground underline-offset-2 hover:underline"
                onClick={() => dismiss(item.id)}
              >
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}

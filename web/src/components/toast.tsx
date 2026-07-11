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
      setItems((prev) => [...prev.slice(-3), { id, message, tone }]);
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
              "pointer-events-auto chime-rise w-full max-w-sm rounded-lg border px-4 py-3 text-sm shadow-sm backdrop-blur-sm",
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

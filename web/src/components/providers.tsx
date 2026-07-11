"use client";

import type { ReactNode } from "react";

import { ToastProvider } from "@/components/toast";

export function Providers({ children }: { children: ReactNode }) {
  return <ToastProvider>{children}</ToastProvider>;
}

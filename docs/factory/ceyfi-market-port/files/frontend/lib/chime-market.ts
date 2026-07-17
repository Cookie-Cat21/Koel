/**
 * Ceyfi Market client — talks to Ceyfi backend `/api/market/*`
 * (mock Chime payloads, or live proxy when CHIME_API_BASE is set on the backend).
 */
import { authHeaders } from "@/lib/auth";
import { API_BASE, ApiError } from "@/lib/api";

export type MarketWatchItem = {
  symbol: string;
  name?: string | null;
  price?: number | null;
  change_pct?: number | null;
  volume?: number | null;
};

export type MarketAlert = {
  id: string;
  symbol: string;
  type: string;
  threshold?: number | null;
  active?: boolean;
  created_at?: string;
};

export type MarketFire = {
  id: string;
  alert_id?: string;
  symbol: string;
  type: string;
  title?: string;
  message?: string;
  price?: number | null;
  fired_at?: string;
  delivery_status?: string;
};

async function marketRequest<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { ...authHeaders() },
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new ApiError(res.status, text);
  }
  return res.json();
}

export async function getMarketOverview() {
  return marketRequest<{
    source: string;
    nfa: string;
    watchlist: MarketWatchItem[];
    alerts: MarketAlert[];
    fires: MarketFire[];
    as_of: string;
  }>("/api/market/overview");
}

export async function getMarketWatchlist() {
  return marketRequest<{
    source: string;
    nfa: string;
    items: MarketWatchItem[];
  }>("/api/market/watchlist");
}

export async function getMarketAlerts() {
  return marketRequest<{
    source: string;
    nfa: string;
    items: MarketAlert[];
  }>("/api/market/alerts");
}

export async function getMarketFires() {
  return marketRequest<{
    source: string;
    nfa: string;
    items: MarketFire[];
  }>("/api/market/fires");
}

export async function getMarketFireDetail(fireId: string) {
  return marketRequest<{
    source: string;
    nfa: string;
    fire: MarketFire;
    user_id: string;
    broker_cta: { label: string; hint: string };
  }>(`/api/market/fires/${encodeURIComponent(fireId)}`);
}

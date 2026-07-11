import { headers } from "next/headers";

/**
 * Server-side GET to our own /api/v1/* with the incoming session cookie.
 * Pages stay thin; route handlers own Postgres + auth.
 */
export async function serverApiGet(path: string): Promise<Response> {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
  const proto = h.get("x-forwarded-proto") ?? "http";
  const cookie = h.get("cookie") ?? "";
  const url = path.startsWith("http") ? path : `${proto}://${host}${path}`;
  return fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      cookie,
    },
    cache: "no-store",
  });
}

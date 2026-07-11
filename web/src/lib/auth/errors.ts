import { NextResponse } from "next/server";

const JSON_HEADERS = {
  "Content-Type": "application/json; charset=utf-8",
} as const;

export function jsonError(
  status: number,
  code: string,
  message: string,
): NextResponse {
  return NextResponse.json(
    { error: { code, message } },
    { status, headers: JSON_HEADERS },
  );
}

export function jsonOk(
  body: unknown,
  status: number = 200,
): NextResponse {
  return NextResponse.json(body, { status, headers: JSON_HEADERS });
}

#!/usr/bin/env python3
"""Polite live probe for cse.lk public API endpoints.

Writes:
  samples/<id>.json          truncated response bodies
  catalog/last_probe.json    machine-readable results
  catalog/PROBE_REPORT.md    human summary

Exit 0 if all endpoints match expect_status; 1 otherwise.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "endpoints.yaml"
SAMPLES = ROOT / "samples"
REPORT_JSON = ROOT / "catalog" / "last_probe.json"
REPORT_MD = ROOT / "catalog" / "PROBE_REPORT.md"


def truncate(data: Any, max_bytes: int, list_key: str | None) -> Any:
    raw = json.dumps(data, ensure_ascii=False, default=str)
    if list_key and isinstance(data, dict) and isinstance(data.get(list_key), list):
        rows = data[list_key]
        keep = min(3, len(rows))
        out = dict(data)
        out[list_key] = rows[:keep]
        out["_truncated"] = {
            "list_key": list_key,
            "kept": keep,
            "original_len": len(rows),
        }
        data = out
        raw = json.dumps(data, ensure_ascii=False, default=str)
    if len(raw.encode()) <= max_bytes:
        return data
    # hard trim large nested blobs
    return {
        "_truncated": True,
        "_note": f"payload exceeded {max_bytes} bytes; keys only",
        "keys": list(data.keys()) if isinstance(data, dict) else type(data).__name__,
        "preview": raw[:2000],
    }


def fingerprint(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return {"type": "object", "keys": sorted(data.keys())[:40]}
    if isinstance(data, list):
        sample_keys = (
            sorted(data[0].keys())[:20]
            if data and isinstance(data[0], dict)
            else None
        )
        return {"type": "array", "len": len(data), "item_keys": sample_keys}
    return {"type": type(data).__name__}


def render_body(ep: dict[str, Any], symbol: str, stock_id: str | None) -> dict[str, str] | str | None:
    body = ep.get("body")
    if body is None:
        return None
    if body == {}:
        return {}
    if isinstance(body, dict):
        out: dict[str, str] = {}
        for k, v in body.items():
            s = str(v)
            s = s.replace("{{symbol}}", symbol)
            if "{{stock_id}}" in s:
                if not stock_id:
                    raise RuntimeError("stock_id required but missing")
                s = s.replace("{{stock_id}}", stock_id)
            out[k] = s
        return out
    return body


def main() -> int:
    cfg = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    meta = cfg["meta"]
    base = meta["base_url"].rstrip("/")
    symbol = meta["test_symbol"]
    delay = float(meta.get("delay_seconds", 0.35))
    max_bytes = int(meta.get("max_sample_bytes", 12000))
    headers = dict(meta.get("headers") or {})

    SAMPLES.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    stock_id: str | None = None
    failed = 0

    with httpx.Client(timeout=45.0, follow_redirects=True, headers=headers) as client:
        for ep in cfg["endpoints"]:
            eid = ep["id"]
            path = ep["path"]
            url = f"{base}{path}"
            method = ep["method"].upper()
            ctype = ep.get("content_type", "json")
            expect = set(ep.get("expect_status") or [200])
            row: dict[str, Any] = {
                "id": eid,
                "path": path,
                "method": method,
                "category": ep.get("category"),
                "summary": ep.get("summary"),
            }
            try:
                if ep.get("resolve_stock_id_from") and not stock_id:
                    raise RuntimeError("stock_id not resolved yet — order catalog correctly")

                kwargs: dict[str, Any] = {}
                if method == "GET":
                    kwargs["params"] = ep.get("query") or {}
                else:
                    body = render_body(ep, symbol, stock_id)
                    if ctype == "form":
                        kwargs["data"] = body if body is not None else {}
                    elif ctype == "json":
                        kwargs["json"] = body if body is not None else {}
                    elif ctype == "none":
                        pass

                resp = client.request(method, url, **kwargs)
                row["status"] = resp.status_code
                row["ok"] = resp.status_code in expect
                if not row["ok"]:
                    failed += 1
                    row["error"] = f"unexpected status {resp.status_code}; expected {sorted(expect)}"

                data: Any
                if resp.status_code == 204 or not resp.content:
                    data = {"_empty": True, "_http_status": resp.status_code}
                else:
                    try:
                        data = resp.json()
                    except Exception:
                        data = {
                            "_non_json": True,
                            "text_preview": resp.text[:500],
                            "_http_status": resp.status_code,
                        }

                # capture stock id from company info
                if eid == "companyInfoSummery" and isinstance(data, dict):
                    info = data.get("reqSymbolInfo") or {}
                    if isinstance(info, dict) and info.get("id") is not None:
                        stock_id = str(info["id"])
                        row["resolved_stock_id"] = stock_id

                sample = {
                    "_probe": {
                        "id": eid,
                        "url": url,
                        "method": method,
                        "status": resp.status_code,
                        "verified_at": datetime.now(UTC).isoformat(),
                        "fingerprint": fingerprint(data if not isinstance(data, dict) or "_empty" not in data else data),
                    },
                    "response": truncate(data, max_bytes, ep.get("truncate_list_key")),
                }
                (SAMPLES / f"{eid}.json").write_text(
                    json.dumps(sample, indent=2, ensure_ascii=False, default=str) + "\n",
                    encoding="utf-8",
                )
                row["fingerprint"] = sample["_probe"]["fingerprint"]
                row["sample"] = f"samples/{eid}.json"
            except Exception as exc:  # noqa: BLE001 — collect all probe errors
                failed += 1
                row["ok"] = False
                row["status"] = None
                row["error"] = str(exc)
            results.append(row)
            time.sleep(delay)

    payload = {
        "probed_at": datetime.now(UTC).isoformat(),
        "base_url": base,
        "symbol": symbol,
        "stock_id": stock_id,
        "failed": failed,
        "passed": len(results) - failed,
        "total": len(results),
        "results": results,
        "websocket": cfg.get("websocket"),
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        f"# Probe report",
        "",
        f"**When:** `{payload['probed_at']}`  ",
        f"**Base:** `{base}`  ",
        f"**Symbol:** `{symbol}` stockId=`{stock_id}`  ",
        f"**Result:** {payload['passed']}/{payload['total']} passed "
        f"({failed} failed)",
        "",
        "| ID | Method | Path | Status | OK |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        st = r.get("status")
        ok = "✅" if r.get("ok") else "❌"
        lines.append(
            f"| `{r['id']}` | {r['method']} | `{r['path']}` | {st} | {ok} |"
        )
        if r.get("error"):
            lines.append(f"| | | | | `{r['error']}` |")
    lines.append("")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(REPORT_MD.read_text(encoding="utf-8"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

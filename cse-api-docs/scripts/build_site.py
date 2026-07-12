#!/usr/bin/env python3
"""Build a simple static HTML documentation site from catalog + samples."""

from __future__ import annotations

import html
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog" / "endpoints.yaml"
LAST = ROOT / "catalog" / "last_probe.json"
SAMPLES = ROOT / "samples"
SITE = ROOT / "site"
DOCS = ROOT / "docs"


CSS = """
:root {
  --bg: #0f1419;
  --panel: #1a222c;
  --text: #e7ecf1;
  --muted: #9aa7b5;
  --accent: #3dbea0;
  --bad: #e57373;
  --ok: #81c784;
  --border: #2a3542;
  --mono: "JetBrains Mono", ui-monospace, monospace;
  --sans: "IBM Plex Sans", system-ui, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: var(--sans); background: var(--bg); color: var(--text);
  line-height: 1.55;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
header {
  padding: 1.5rem 1.25rem 1rem; border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, #152028, var(--bg));
}
header h1 { margin: 0 0 .35rem; font-size: 1.6rem; letter-spacing: -.02em; }
header p { margin: 0; color: var(--muted); max-width: 52rem; }
nav {
  display: flex; flex-wrap: wrap; gap: .75rem 1.25rem; padding: .75rem 1.25rem;
  border-bottom: 1px solid var(--border); background: var(--panel);
  position: sticky; top: 0; z-index: 2;
}
main { padding: 1.25rem; max-width: 960px; margin: 0 auto; }
.card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
  padding: 1rem 1.1rem; margin: 0 0 1rem;
}
.card h2 { margin: 0 0 .5rem; font-size: 1.15rem; }
.meta { color: var(--muted); font-size: .92rem; }
.badge {
  display: inline-block; font-size: .75rem; padding: .15rem .45rem;
  border-radius: 999px; border: 1px solid var(--border); margin-right: .35rem;
  font-family: var(--mono);
}
.badge.ok { color: var(--ok); border-color: #356b3d; }
.badge.bad { color: var(--bad); border-color: #7a3b3b; }
.badge.cat { color: var(--accent); }
table { width: 100%; border-collapse: collapse; font-size: .92rem; }
th, td { text-align: left; padding: .45rem .4rem; border-bottom: 1px solid var(--border); vertical-align: top; }
th { color: var(--muted); font-weight: 600; }
code, pre { font-family: var(--mono); font-size: .85rem; }
pre {
  background: #0b1015; border: 1px solid var(--border); border-radius: 8px;
  padding: .85rem; overflow: auto; max-height: 320px;
}
footer { padding: 2rem 1.25rem; color: var(--muted); font-size: .9rem; border-top: 1px solid var(--border); }
h3 { margin: 1.2rem 0 .4rem; font-size: 1rem; }
.grid { display: grid; gap: .75rem; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
.stat { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: .85rem; }
.stat b { display: block; font-size: 1.4rem; color: var(--accent); }
"""


def md_to_html_basic(text: str) -> str:
    """Very small markdown subset → HTML (headings, lists, code fences, paragraphs)."""
    lines = text.splitlines()
    out: list[str] = []
    in_code = False
    in_ul = False
    for line in lines:
        if line.startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                if in_ul:
                    out.append("</ul>")
                    in_ul = False
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        if line.startswith("# "):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("|"):
            # skip table lines in basic converter — already rendered elsewhere
            continue
        elif line.startswith("- "):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline(line[2:])}</li>")
        elif line.strip() == "":
            if in_ul:
                out.append("</ul>")
                in_ul = False
        else:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append(f"<p>{inline(line)}</p>")
    if in_code:
        out.append("</code></pre>")
    if in_ul:
        out.append("</ul>")
    return "\n".join(out)


def inline(s: str) -> str:
    import re

    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    return s


def page(title: str, body: str, root: str = ".") -> str:
    nav = f"""
<nav>
  <a href="{root}/index.html">Home</a>
  <a href="{root}/endpoints/index.html">Endpoints</a>
  <a href="{root}/websocket.html">WebSocket</a>
  <a href="{root}/ethics.html">Ethics</a>
  <a href="{root}/examples.html">Examples</a>
  <a href="{root}/compare.html">vs GH0STH4CKER</a>
  <a href="{root}/probe.html">Last probe</a>
</nav>"""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)} · CSE API Docs (unofficial)</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Unofficial CSE API Docs</h1>
  <p>Live-probed documentation for <code>https://www.cse.lk/api</code>. Not affiliated with the Colombo Stock Exchange.</p>
</header>
{nav}
<main>
{body}
</main>
<footer>
  MIT-licensed harness · Not financial advice · <a href="{root}/ethics.html">Ethics</a> ·
  Generated {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")}
</footer>
</body>
</html>
"""


def curl_example(base: str, ep: dict) -> str:
    path = ep["path"]
    method = ep["method"]
    url = f"{base}{path}"
    if method == "GET":
        q = ep.get("query") or {}
        if q:
            qs = "&".join(f"{k}={v}" for k, v in q.items())
            url = f"{url}?{qs}"
        return f"curl -sS '{url}' \\\n  -H 'Origin: https://www.cse.lk' -H 'Referer: https://www.cse.lk/'"
    ctype = ep.get("content_type")
    if ctype == "form":
        body = ep.get("body") or {}
        if body == {}:
            data = "''"
        else:
            data = "&".join(f"{k}={v}" for k, v in body.items())
            data = f"'{data}'"
        return (
            f"curl -sS -X POST '{url}' \\\n"
            f"  -H 'Content-Type: application/x-www-form-urlencoded' \\\n"
            f"  -H 'Origin: https://www.cse.lk' -H 'Referer: https://www.cse.lk/' \\\n"
            f"  -d {data}"
        )
    return (
        f"curl -sS -X POST '{url}' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -H 'Origin: https://www.cse.lk' -H 'Referer: https://www.cse.lk/' \\\n"
        f"  -d '{{}}'"
    )


def main() -> None:
    cfg = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    base = cfg["meta"]["base_url"]
    probe = {}
    if LAST.exists():
        probe = json.loads(LAST.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in probe.get("results", [])}

    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "endpoints").mkdir(exist_ok=True)

    # index
    cats: dict[str, list] = defaultdict(list)
    for ep in cfg["endpoints"]:
        cats[ep.get("category", "other")].append(ep)

    stats = f"""
<div class="grid">
  <div class="stat"><b>{len(cfg['endpoints'])}</b>HTTP endpoints catalogued</div>
  <div class="stat"><b>{probe.get('passed', '—')}</b>last probe passed</div>
  <div class="stat"><b>{len(cfg.get('websocket', {}).get('topics', []))}</b>STOMP topics</div>
  <div class="stat"><b>{probe.get('probed_at', 'not probed')[:19] if probe.get('probed_at') else 'not probed'}</b>last verified</div>
</div>
"""
    index_body = stats + """
<div class="card">
  <h2>What this is</h2>
  <p class="meta">Deeper than name-only community lists: request shapes, failure modes,
  truncated samples, and a STOMP map reverse-engineered from the official site’s JS.
  Prefer polite HTTP polling for bots; use WebSocket for live boards.</p>
</div>
<div class="card">
  <h2>Categories</h2>
  <ul>
"""
    for cat, eps in sorted(cats.items()):
        index_body += f"<li><a href='endpoints/index.html#{html.escape(cat)}'><code>{html.escape(cat)}</code></a> — {len(eps)} endpoints</li>\n"
    index_body += "</ul></div>"
    (SITE / "index.html").write_text(page("Home", index_body), encoding="utf-8")

    # endpoints index + detail pages
    ep_index = ["<h2>Endpoint catalog</h2>"]
    for cat, eps in sorted(cats.items()):
        ep_index.append(f"<h3 id='{html.escape(cat)}'>{html.escape(cat)}</h3><table><tr><th>ID</th><th>Method</th><th>Path</th><th>Probe</th></tr>")
        for ep in eps:
            rid = ep["id"]
            st = by_id.get(rid, {})
            badge = (
                f"<span class='badge ok'>{st.get('status')}</span>"
                if st.get("ok")
                else (
                    f"<span class='badge bad'>{st.get('status')}</span>"
                    if st
                    else "<span class='badge'>unprobed</span>"
                )
            )
            ep_index.append(
                f"<tr><td><a href='{html.escape(rid)}.html'><code>{html.escape(rid)}</code></a></td>"
                f"<td>{ep['method']}</td><td><code>{html.escape(ep['path'])}</code></td><td>{badge}</td></tr>"
            )
        ep_index.append("</table>")
    (SITE / "endpoints" / "index.html").write_text(
        page("Endpoints", "\n".join(ep_index), root=".."), encoding="utf-8"
    )

    for ep in cfg["endpoints"]:
        rid = ep["id"]
        st = by_id.get(rid, {})
        sample_path = SAMPLES / f"{rid}.json"
        sample_html = "<p class='meta'>No sample yet — run <code>python3 scripts/probe.py</code>.</p>"
        if sample_path.exists():
            sample_html = f"<pre>{html.escape(sample_path.read_text(encoding='utf-8')[:8000])}</pre>"
        fails = ep.get("fails") or []
        fail_html = "".join(f"<li>{html.escape(f)}</li>" for f in fails) or "<li>None recorded</li>"
        fields = ep.get("fields") or []
        field_html = "".join(
            f"<li><code>{html.escape(f.get('path',''))}</code>"
            + (f" — {html.escape(f['note'])}" if f.get("note") else "")
            + "</li>"
            for f in fields
        ) or "<li class='meta'>See sample JSON</li>"
        body = f"""
<div class="card">
  <h2><code>{html.escape(ep['method'])} {html.escape(ep['path'])}</code></h2>
  <p><span class="badge cat">{html.escape(ep.get('category',''))}</span>
  {"<span class='badge ok'>probe ok</span>" if st.get("ok") else "<span class='badge bad'>probe issue / unprobed</span>"}
  </p>
  <p>{html.escape(ep.get("summary") or "")}</p>
  <p class="meta">Used by UI: {html.escape(ep.get("used_by_ui") or "—")}</p>
  <p class="meta">Last probe status: {html.escape(str(st.get("status")))} · expect {html.escape(str(ep.get("expect_status")))}</p>
</div>
<div class="card">
  <h3>curl</h3>
  <pre>{html.escape(curl_example(base, ep))}</pre>
</div>
<div class="card">
  <h3>Known failures</h3>
  <ul>{fail_html}</ul>
  <h3>Fields</h3>
  <ul>{field_html}</ul>
</div>
<div class="card">
  <h3>Sample</h3>
  {sample_html}
</div>
"""
        (SITE / "endpoints" / f"{rid}.html").write_text(
            page(rid, body, root=".."), encoding="utf-8"
        )

    # websocket / ethics from md
    (SITE / "websocket.html").write_text(
        page("WebSocket", md_to_html_basic((DOCS / "WEBSOCKET.md").read_text(encoding="utf-8"))),
        encoding="utf-8",
    )
    (SITE / "ethics.html").write_text(
        page("Ethics", md_to_html_basic((DOCS / "ETHICS.md").read_text(encoding="utf-8"))),
        encoding="utf-8",
    )
    (SITE / "compare.html").write_text(
        page("Compare", md_to_html_basic((DOCS / "COMPARE.md").read_text(encoding="utf-8"))),
        encoding="utf-8",
    )

    # examples
    examples = f"""
<div class="card">
  <h2>Python — company quote</h2>
  <pre>{html.escape((ROOT / "examples/python/quote.py").read_text(encoding="utf-8"))}</pre>
</div>
<div class="card">
  <h2>Python — trade summary (bulk)</h2>
  <pre>{html.escape((ROOT / "examples/python/trade_summary.py").read_text(encoding="utf-8"))}</pre>
</div>
<div class="card">
  <h2>curl cheat sheet</h2>
  <pre>{html.escape((ROOT / "examples/curl/cheat_sheet.sh").read_text(encoding="utf-8"))}</pre>
</div>
"""
    (SITE / "examples.html").write_text(page("Examples", examples), encoding="utf-8")

    # probe page
    if LAST.exists():
        probe_body = f"<div class='card'><pre>{html.escape(LAST.read_text(encoding='utf-8')[:20000])}</pre></div>"
        md = ROOT / "catalog" / "PROBE_REPORT.md"
        if md.exists():
            probe_body = md_to_html_basic(md.read_text(encoding="utf-8")) + probe_body
    else:
        probe_body = "<p>No probe yet.</p>"
    (SITE / "probe.html").write_text(page("Probe", probe_body), encoding="utf-8")

    # copy changelog
    (SITE / "changelog.html").write_text(
        page("Changelog", md_to_html_basic((DOCS / "CHANGELOG.md").read_text(encoding="utf-8"))),
        encoding="utf-8",
    )

    print(f"Built site → {SITE}")


if __name__ == "__main__":
    main()

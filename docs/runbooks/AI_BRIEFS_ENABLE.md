# AI briefs — controlled enable checklist

Default stays **off** (`AI_BRIEFS_ENABLED=0`). Do not flip the code default.
Full context: [TIJORI.md](TIJORI.md) · deploy: [PRODUCTION.md](PRODUCTION.md).

## Preconditions

1. Migrations applied (`python3 -m koel migrate`).
2. Watchlist (or board) disclosures have `pdf_url` where possible
   (`python3 -m koel drain-pdfs --limit 20`).
3. One poller/both replica only during the soak (advisory lock + brief cap
   assume a single leader for CSE ticks; dual replicas still skip on lock but
   brief drain can race — keep one).

## Enable (staging → prod)

```bash
# Leave off until keys + soak ready:
AI_BRIEFS_ENABLED=0

# Controlled flip:
AI_BRIEFS_ENABLED=1
AI_API_KEY=…                 # primary; backups alone also satisfy briefs_enabled()
AI_PROVIDER=gemini           # or: groq | openrouter
AI_MODEL=gemini-2.0-flash    # match provider
# Optional failover (429 / 5xx / timeout only):
# AI_BACKUP_PROVIDERS=groq,openrouter
# AI_BACKUP_API_KEYS=…,…
# AI_BACKUP_MODELS=llama-3.3-70b-versatile,openai/gpt-4o-mini
```

## Rate / cost guardrails

| Env | Default | Role |
|---|---|---|
| `AI_MAX_BRIEFS_PER_DAY` | `50` | Hard daily claim budget |
| `AI_BRIEF_SLEEP_SECONDS` | `0.5` | Pause between LLM calls in a drain |
| `AI_HTTP_TIMEOUT_SECONDS` | `30` | Per-call HTTP timeout |
| `AI_MAX_INPUT_CHARS` | `12000` | Truncate filing text before provider |

Start with a low `AI_MAX_BRIEFS_PER_DAY` (e.g. `10`) for the first day.

## Soak steps

1. Set keys + `AI_BRIEFS_ENABLED=1` on **one** replica.
2. `python3 -m koel drain-briefs --limit 5` — confirm `ready` rows, no error storm.
3. Telegram `/brief SYMBOL` for a ready symbol (read-only; no LLM).
4. Leave poller running; watch brief_queue health + provider 429s.
5. If noisy: set `AI_BRIEFS_ENABLED=0` (rollback). Existing `ready` briefs remain readable.

## Rollback

```bash
AI_BRIEFS_ENABLED=0
```

No schema rollback required. Pending claims stop; Telegram live alerts keep working.

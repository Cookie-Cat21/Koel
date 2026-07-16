# Security rotation checklist (ops)

Use after any credential paste, leak, or audit finding **S-02 / S-03 / S-14**.

Agent code cannot rotate BotFather / Neon / Groq / Vercel secrets for you.

## 1. Rotate immediately

| Secret | Where | Action |
|--------|-------|--------|
| `TELEGRAM_BOT_TOKEN` | @BotFather → Revoke → new token | Update Vercel, GitHub Actions, Cloud Agent env |
| Neon `DATABASE_URL` | Neon console → reset password / rotate | Update all consumers; old URL dies |
| Groq `AI_API_KEY` (+ backups) | Groq console | Revoke leaked keys; set new primary + backups |
| `DASH_SESSION_SECRET` | `openssl rand -hex 32` | Update Vercel/web env — **all sessions invalidate** |

Never paste new values into chat. Prefer secret managers / CI env UIs.

## 2. Production demo auth (S-02)

On **https://chime-cse.vercel.app** (Production):

```text
DASH_DEMO_AUTH=0
```

Prefer Telegram Login Widget:

```text
DASH_TELEGRAM_LOGIN=1
```

(plus BotFather domain allowlist for the Vercel host).

Keep `DASH_DEMO_AUTH=1` only on Cloud Agent / staging.

## 3. Ops health detail (S-05)

```text
DASH_OPS_TELEGRAM_IDS=<your telegram id>
```

Empty = every logged-in user gets **summary** health only (no delivery / poller proxy).

## 4. After rotation

1. Redeploy Vercel / restart poller+bot with new env.
2. Sign in again (session secret change).
3. `POST /api/v1/auth/logout-all` from Settings if a cookie may have been stolen.
4. Confirm demo login returns 403 on production.

## Related

- Audit: `docs/factory/SECURITY_AUDIT_2026-07-16.md`
- API: `docs/factory/API_CONTRACT_V1.md`

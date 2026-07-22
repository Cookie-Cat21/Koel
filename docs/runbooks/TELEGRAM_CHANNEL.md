# Public koel Telegram channel (W7)

Automated **open pulse** (~09:35 SLT) and **close summary** (after 14:30 SLT)
posted to a public channel from the poller. Bodies are built from Postgres facts
only (indexes, top movers, disclosure count) — no LLM.

## Setup

1. **Create a Telegram channel** (public or private) for koel market posts.
2. **Add the koel bot as an administrator** with permission to post messages
   (`Post Messages`). The bot must be able to send to the channel.
3. **Get the channel id.** Channels use a negative chat id (e.g. `-100…`).
   Forward a channel message to `@userinfobot` / `@getidsbot`, or inspect
   `getUpdates` after posting once while the bot is admin.
4. **Set the env** (see also `.env.example`):

   ```bash
   TELEGRAM_PUBLIC_CHANNEL_ID=-100xxxxxxxxxx
   # Optional: deep-link CTA in posts
   # TELEGRAM_BOT_USERNAME=your_bot_username
   ```

5. **Restart the poller** (`python3 -m koel poller` or `both`) so it picks up
   the env. Process-lifetime flags track “already sent today” in memory —
   a restart may post again the same Colombo day if data is available.

## Behaviour

| Post | When | Content |
|---|---|---|
| Open pulse | First successful market-hours tick **after 09:35 SLT** (weekdays) | ASPI / S&P SL20 + “CSE is open” + NFA + bot CTA |
| Close summary | Off-hours ticks **after 14:30 SLT** (same path as EOD digest) | Index moves, top movers, disclosures today + NFA + CTA |

If `TELEGRAM_PUBLIC_CHANNEL_ID` is unset or empty, channel posting is a no-op.
If index/mover data is missing, builders return `None` and nothing is sent
(fail soft).

## Notes

- Not financial advice — every post ends with the standard NFA line.
- Do not use buy/sell language in channel copy.
- Degraded-feed status notices still use optional `TELEGRAM_STATUS_CHAT_ID`
  (ops), separate from this public funnel channel.

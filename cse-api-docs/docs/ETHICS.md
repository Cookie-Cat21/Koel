# Ethics & compliance

This project documents **public** HTTP/WebSocket endpoints used by
[https://www.cse.lk](https://www.cse.lk). It is **unofficial** and not endorsed by the
Colombo Stock Exchange.

## Rules

1. **Public JSON/WS only** — do not scrape HTML; do not scrape competitor sites.
2. **Polite rate limits** — default probe delay ≥ 350ms; never hammer production.
3. **No auth abuse** — account/OTP endpoints are listed as “observed only”. Do not
   automate sign-up, credential stuffing, or session theft.
4. **Not financial advice** — examples are for engineering/education. CSE / SEC Sri
   Lanka market-misconduct rules still apply to how *you* use data.
5. **No stability claims** — undocumented APIs change; always re-probe.
6. **Attribution** — when redistributing docs, keep this ethics page and MIT notice.

## Relationship to Chime

[Chime](https://github.com/Cookie-Cat21/Chime) is a Telegram alerting product that
consumes a subset of these endpoints. This docs kit is a **sibling** community
resource, not a trading terminal and not investment advice.

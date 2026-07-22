/**
 * In-app Help copy — glossary, how-it-works, and calculation explainers.
 * Keep NFA-safe: facts and mechanics only; never buy/sell / “best to invest”.
 */

export type HelpFaqItem = {
  question: string;
  /** Plain text; use blank lines (`\\n\\n`) for separate paragraphs. */
  answer: string;
};

export type HelpTopic = {
  id: string;
  title: string;
  summary: string;
  items: readonly HelpFaqItem[];
};

export const HELP_TOPICS: readonly HelpTopic[] = [
  {
    id: "getting-started",
    title: "Getting started",
    summary: "What koel is, how the dash and Telegram fit together.",
    items: [
      {
        question: "What is koel?",
        answer:
          "koel is a Colombo Stock Exchange (CSE) dashboard for browsing symbols, watching what you care about, and managing alert rules — with Telegram push when something fires.\n\nThe web app is the daily surface. Telegram is how you hear the market when the browser is closed. Neither is investment advice.",
      },
      {
        question: "Cake vs cherry — dash vs Telegram?",
        answer:
          "Cake = the dashboard (browse, watchlist, alerts, scores, health). Cherry = Telegram push when a rule fires.\n\nSame Postgres truth for both. Creating an alert in the dash also puts the symbol on your watchlist so the poller keeps snapshots for it.",
      },
      {
        question: "Watchlist vs alerts vs history?",
        answer:
          "Watchlist = symbols you follow (prices and disclosures koel keeps fresh).\n\nAlerts = active rules (price cross, daily move, disclosure, volume, and more). History = past fires that koel already sent or recorded.\n\nExample: add JKH.N0000 to Watchlist to track it; create “JKH.N0000 above 200” under Alerts to get a Telegram ping when that cross happens.",
      },
      {
        question: "Does the dashboard call the CSE site live?",
        answer:
          "No. The dash reads Postgres only. A separate poller fetches CSE JSON during market hours and writes snapshots. If data looks stale, check Health — not your browser network tab for the exchange site.",
      },
      {
        question: "Where do I learn about a single company page?",
        answer:
          "Open any symbol from Browse or Watchlist. That company page shows the quote, chart, returns, tech labels, filing metrics, Book (NAV / P/B / ROE), dividends, price compare, and disclosures.\n\nJump to Company page, Quote chrome, Charts, and the other company topics in Help for field-by-field explainers.",
      },
      {
        question: "What does Search / Ctrl K do?",
        answer:
          "The Search control (Ctrl/Cmd+K) opens a command palette that looks up CSE symbols from koel’s stocks table and jumps to the company page. Arrow keys + Enter select a result. It is symbol search — not a full-document Help search (use Help topics for that).",
      },
    ],
  },
  {
    id: "prices",
    title: "Prices & market fields",
    summary: "Last price, change %, volume, sparklines, and freshness.",
    items: [
      {
        question: "What do price, change, and change % mean?",
        answer:
          "Price is the latest last-traded price koel stored for that symbol.\n\nChange is absolute move vs previous close (same units as price). Change % is that move as a percent of previous close.\n\nExample: previous close 100.00, last 102.50 → change +2.50, change % +2.50%. If CSE omits change %, koel may derive it as (price − previous_close) / previous_close × 100.",
      },
      {
        question: "What is Prev close and market cap?",
        answer:
          "Prev close on the company page is derived as last price − change when change exists (shown as — if change is missing).\n\nMarket cap is the latest stored `market_cap` from the price snapshot when CSE provided it — compact formatted (e.g. billions). It is not recalculated from shares outstanding in the dash.",
      },
      {
        question: "What is volume?",
        answer:
          "Shares traded in the session (or latest snapshot window koel stored). Volume alerts compare current volume to a recent average — see Alert types.",
      },
      {
        question: "What does the sparkline show?",
        answer:
          "A short price-over-time sketch from stored snapshots or daily bars — not a full technical-analysis chart suite. On company pages the hero prefers daily OHLC candles when enough bars exist; see Charts.",
      },
      {
        question: "Why is a quote missing or stale?",
        answer:
          "Common causes: symbol not on any watchlist (poller only persists watched names for some paths), market closed, poller idle outside 09:30–14:30 Asia/Colombo weekdays, or a CSE fetch failure.\n\nOpen Health for poller status and snapshot age. Symbol pages also show data-quality notices when rows are empty or old — see Data quality.",
      },
    ],
  },
  {
    id: "symbol-page",
    title: "Company (symbol) page",
    summary: "Layout of /symbols/… — quote, chart, strips, filings, compare.",
    items: [
      {
        question: "What is on a company page?",
        answer:
          "Top: symbol, name/sector, market open/closed chip, soft refresh chip, Watch, New alert, Dividends, Ownership map, People.\n\nThen: last price card with chart, Prev close / Volume / Market cap, period returns (1W–1Y), tech labels, filing EPS strip, Book (NAV / P/B / ROE), dividend strip when DPS exists, price compare, filing metrics + brief, and the disclosures timeline.\n\nResearch scores live on Signal Board — not as a score strip on the company page today.",
      },
      {
        question: "What does Watch on a symbol do?",
        answer:
          "Watch adds the symbol to your watchlist so the poller keeps price snapshots and disclosure attention for it. Unwatch removes it. Telegram pushes still need an alert rule — watching alone does not ping every tick.",
      },
      {
        question: "Why “Symbol not found”?",
        answer:
          "Only symbols already in koel’s `stocks` table open a company page. Browse after a market poll, watch via Telegram `/watch SYMBOL`, or wait until the poller has seen the ticker. Unknown strings are rejected — the dash never invents a blank company shell.",
      },
      {
        question: "Can I deep-link chart range or compare peers?",
        answer:
          "Yes. Company URLs accept query helpers such as `?range=1M` or `?range=1Y`, `?expandChart=1` to open the chart dialog, `?compare=PEER1,PEER2` (up to three peers plus the base), and `?category=…` to pre-filter disclosures.",
      },
    ],
  },
  {
    id: "symbol-quote",
    title: "Quote chrome & session chips",
    summary: "Today vs dated change, stale vs closed, refresh labels.",
    items: [
      {
        question: "Why does change say “today”, a date, or “session”?",
        answer:
          "CSE change is vs previous close for that snapshot’s Colombo session — not always calendar “today.” koel labels the scope from the snapshot’s Asia/Colombo date: “today” when it matches today’s Colombo date, otherwise a short date like “Jul 17”, or “session” if the stamp is unclear.",
      },
      {
        question: "What do · stale and · market closed mean on last price?",
        answer:
          "· market closed — koel’s clock fence says the CSE cash session is shut (about 09:30–14:30 SLT weekdays) and a last print is still shown.\n\n· stale — the stored tick is more than about 24 hours old while the session looks open (poller paused or symbol not watched). This is separate from the small header refresh chip’s shorter “Stale” (about 3 minutes).",
      },
      {
        question: "Is “Market open” from the live exchange?",
        answer:
          "No. The market open/closed chip is a client clock fence for 09:30–14:30 Asia/Colombo on weekdays — not a live CSE marketStatus probe. Treat it as session guidance for the dash, not an exchange official status feed.",
      },
      {
        question: "What do Just updated / Updated / Stale mean on Refresh?",
        answer:
          "On Overview, Browse, Watchlist, and company pages, PriceRefresh soft-reloads about every 15 seconds and ages the newest snapshot: Just updated → Updated Ns / Xm ago. Around 3+ minutes the chip uses a stale tone (“Updated Xm ago”); the word Stale / Down-style aging kicks in around 15+ minutes while the session looks open. Closed · Xm appears when the clock fence says closed.\n\nThat chip is not the same as the 24h “· stale” on the last-price eyebrow.",
      },
      {
        question: "Why don’t Context / Appetite show a refresh chip?",
        answer:
          "Those pages use a silent soft reload about every 60 seconds (SoftPageRefresh) with no age chip. Price-led pages show the LiveIndicator aged off the newest snapshot instead.",
      },
    ],
  },
  {
    id: "symbol-charts",
    title: "Charts & ranges",
    summary: "Candles vs sparkline, 1D–1Y, window OHLCV, Live.",
    items: [
      {
        question: "Candles vs sparkline?",
        answer:
          "When koel has enough daily bars, the company hero shows daily OHLC candlesticks (expand for more ranges). If daily path history is thin (under 2 bars), it falls back to a tick sparkline from stored snapshots.\n\nEmpty chart copy about path-backfill means daily bars are not stored yet — not that the company has no price forever.",
      },
      {
        question: "What do 1D / 1M / 3M / 6M / 1Y mean?",
        answer:
          "Expand ranges opens a dialog with session-depth windows (about 1 day of ticks, or ~22 / 66 / 132 / 260 sessions for 1M–1Y). Default SSR paint is often 3M. These are research windows over stored Postgres path data — not a brokerage chart package.",
      },
      {
        question: "Are charts split-adjusted?",
        answer:
          "When koel has a stored corporate action (CSE subdivision/consolidation filing or a detected near-integer session price cliff), daily candles and period returns use split-adjusted closes so a 1:3 subdivision does not look like a −67% crash. Raw CSE closes remain in Postgres; the API can return them with `?adjusted=0`.\n\nAdjustment is research-only and may miss silent consolidations until a filing or price cliff is stored. Last trade on the quote card stays the live unadjusted board price.",
      },
      {
        question: "When is 1D Intraday vs Daily?",
        answer:
          "1D prefers today’s Colombo ticks when there are enough prints to build candles (koel looks for a richer tick set, otherwise shows “Few ticks · showing recent daily”). A Live badge can poll ticks every ~20s when the session looks open and the mode is intraday.",
      },
      {
        question: "Are dialog Open / High / Low / Close / Vol the day quote?",
        answer:
          "No — those stats are over the selected chart window. The change shown in the expand header is last close − first close of that window, which can differ from the quote card’s session change vs previous close.\n\nCandle color is green/red vs the prior close in the series; missing CSE opens may fill the body against prior close.",
      },
    ],
  },
  {
    id: "symbol-forecast",
    title: "Forecast overlay on a symbol",
    summary: "Dashed path, Selective gates, confidence bands.",
    items: [
      {
        question: "What is the dashed forecast line?",
        answer:
          "An optional model path from koel’s stored forecast for that symbol — dashed overlay on the sparkline / expand chart. Toggle Show forecast on or off. Auto-on can happen for selective gates or a high confidence band.\n\nResearch only — not a price target or tip. When there are no stored points, the control shows Forecast — none.",
      },
      {
        question: "What do Selective ~90% / ~73% / LTR / Always-on mean?",
        answer:
          "Gate badges describe which historical filter allowed the overlay to speak:\n\n• Selective ~90% (gated_p90 / hpe_p90)\n• Selective ~73% (gated_c55 / gated)\n• LTR rank + vol (gated_ltr)\n• Always-on ~60% (always_on)\n\nPercents are historical out-of-sample hit-rate style labels for the gate — not guarantees for the next move. Spoke on Signal Board means a selective gate cleared; Silent means no selective emit.",
      },
      {
        question: "What is High / Medium / Low confidence?",
        answer:
          "A model self-check band (sometimes with a confidence %). It describes how the forecast row graded itself — not certainty that price will follow the dashed path.",
      },
    ],
  },
  {
    id: "symbol-returns-tech",
    title: "Period returns & tech labels",
    summary: "1W–1Y math plus SMA50, ATR, MACD, Bollinger, 52W.",
    items: [
      {
        question: "How are 1W / 1M / 3M / 1Y returns calculated?",
        answer:
          "Percent change of daily closes vs about 5 / 22 / 66 sessions ago. 1Y prefers ~365 calendar days (with slack) when trade dates exist, else about 220 sessions — CSE public path history is roughly one year, so koel does not demand a full NYSE-style 252-session year.\n\nWhen corporate actions are known, the company page uses the same split-adjusted closes as the chart (so a share subdivision does not invent a huge negative 1Y). Example: close 100 → 110 over 22 sessions → 1M +10%. Null means history is too short. Research labels only.",
      },
      {
        question: "What is SMA50?",
        answer:
          "Percent of last close vs a 50-day simple moving average: (close − SMA50) / |SMA50| × 100. Needs 50 daily bars. Observational — not a buy/sell rule.",
      },
      {
        question: "What is ATR?",
        answer:
          "14-period average true range as a percent of last close. A volatility label for the recent path — not a stop-loss recommendation.",
      },
      {
        question: "What does MACD BULL / BEAR mean?",
        answer:
          "MACD line (EMA12 − EMA26) vs its signal EMA9. Last difference ≥ 0 → BULL, else BEAR. Needs enough closes (~35). Observational only — not advice to trade the cross.",
      },
      {
        question: "What do BB ABOVE / BELOW / MID / SQZ mean?",
        answer:
          "20-day Bollinger bands (±2σ). SQZ when band width is under about 4% of the mean (tight bands). Otherwise ABOVE / BELOW / MID describes where the last close sits vs the bands.",
      },
      {
        question: "What is 52W %?",
        answer:
          "Where the last close sits in the recent high–low window (up to ~252 sessions): (close − low) / (high − low) × 100. Near 100 means close to the window high; near 0 near the window low. CSE path depth may be shorter than a full calendar 52 weeks.",
      },
    ],
  },
  {
    id: "filing-metrics",
    title: "Filing metrics & briefs",
    summary: "EPS / revenue / profit extracts, YoY quality, AI briefs.",
    items: [
      {
        question: "Where do EPS, revenue, and profit come from?",
        answer:
          "Parsed from CSE financial-statement PDFs into `filing_metrics` — not live quotes. The Filing strip shows a compact latest basic EPS (+ YoY when comparable); the Filing metrics panel shows fuller fields (kind, entity, currency, period ended).\n\nAlways verify against the source PDF. Empty metrics are common for warrants, prefs, or names without financial PDFs yet.",
      },
      {
        question: "What do quarterly · group · period ended mean?",
        answer:
          "kind is quarterly / annual / unknown. entity is group / company / unknown (consolidated vs company-only when koel could tell). currency defaults toward LKR when present. period ended is the fiscal period end date from the extract.",
      },
      {
        question: "What is Exact vs Approximate YoY?",
        answer:
          "YoY % only appears when koel matched a prior-year period as exact_yoy or approx_yoy. Other match qualities (missing prior, scale/entity/currency mismatch, skipped) suppress YoY so the dash does not invent a fake growth rate.\n\nΔ is period value vs that matched prior. Approximate means the prior period was the best available match, not a perfect calendar twin.",
      },
      {
        question: "Why are filing metrics or the brief empty?",
        answer:
          "Typical reasons: no financial-statement filings stored, PDFs not enriched yet, extract drain still pending, scanned/unusual PDFs failed parse, or AI briefs flag/key-gated / pending / failed.\n\nData-quality banners summarize the highest-priority issues (see Data quality). Source links stay available even when numbers or briefs are missing.",
      },
    ],
  },
  {
    id: "symbol-fundamentals",
    title: "Book — NAV, P/B, ROE",
    summary: "How the Book strip derives research labels.",
    items: [
      {
        question: "What is NAV here?",
        answer:
          "A scaled equity figure from the ownership-graph company node when confidence is medium or high. Scale: millions × 1e6, thousands × 1e3; unknown mid-range extracts are often treated as Rs millions (CSE annual shorthand). Tiny or low-confidence equity is hidden — koel never invents NAV from price alone.",
      },
      {
        question: "How is P/B calculated?",
        answer:
          "market_cap ÷ NAV when both are positive.\n\nExample: market cap 10,000,000,000 and NAV 5,000,000,000 → P/B 2.00. Missing if mcap or honest NAV is absent.",
      },
      {
        question: "How is ROE calculated?",
        answer:
          "(latest filing profit ÷ NAV) × 100 when both exist. Rough research label from stored extracts — not a full accountant’s ROE schedule.",
      },
      {
        question: "Why is Book empty?",
        answer:
          "No medium/high equity extract for the issuer, equity too small after scaling, or missing market cap / profit for P/B or ROE. Gaps are missing data, not proof the company has zero book value.",
      },
    ],
  },
  {
    id: "symbol-compare",
    title: "Price compare",
    summary: "Overlay peers — Indexed (100) vs Price (LKR).",
    items: [
      {
        question: "How does Price compare work?",
        answer:
          "Overlays up to four symbols using stored tick history (about 180 points). The base company is always included; you can add peers. Shareable via `?compare=PEER1,PEER2` on the company URL.",
      },
      {
        question: "Indexed (100) vs Price (LKR)?",
        answer:
          "Indexed rebases each series’ first tick in the window to 100 so shapes are easier to compare when absolute LKR levels differ. Price (LKR) plots raw last prices — hard to read when one name is 20 and another is 2,000.\n\nScale 1–4 controls how many lines are drawn. Research overlay only — not a pairs-trading tool.",
      },
    ],
  },
  {
    id: "data-quality",
    title: "Data quality notices",
    summary: "Why empty, stale, thin history, or pending extracts.",
    items: [
      {
        question: "What are the yellow/info banners on a company page?",
        answer:
          "Prioritized honesty notices (usually capped around four) explaining why something is empty or old — price freshness first, then filings / metrics / briefs. They are not error toasts for your account.",
      },
      {
        question: "No price / market closed / stale / thin history?",
        answer:
          "No stored price — no tick yet (watch the symbol; wait for session).\n\nMarket closed — expected quiet outside 09:30–14:30 SLT weekdays.\n\nStale price — snapshot older than about a day while the session looks open.\n\nThin price history — fewer than about eight spark points, so the chart looks sparse.",
      },
      {
        question: "No disclosures / financial filings / PDFs / metrics / briefs?",
        answer:
          "Pipeline steps: disclosures stored → financial-statement types present → PDF links enriched → metrics extract → optional AI brief. A banner names the bottleneck (e.g. no PDFs yet, extract failed on scanned pages, brief pending or failed).\n\nMetrics load failed is a fetch error, distinct from “extract returned empty.”",
      },
      {
        question: "Why don’t I see every notice at once?",
        answer:
          "koel shows the highest-priority subset so the page stays readable. Fixing the top issue (e.g. watch the symbol, wait for PDFs) often clears the stack on the next refresh.",
      },
    ],
  },

  {
    id: "overview",
    title: "Overview home",
    summary: "KPIs, indexes, tape pulse, watchlist slice, recent fires.",
    items: [
      {
        question: "What is Overview for?",
        answer:
          "Signed-in home for CSE snapshots koel already stored: market indexes, tape pulse, a slice of your watchlist and armed rules, upcoming XD on watched names, top movers, and recent Telegram fires.\n\nSet rules here; Telegram remains the push path. Research labels only — not tips.",
      },
      {
        question: "What do the KPI cards mean?",
        answer:
          "Watching — how many symbols are on your watchlist (the preview list is capped).\n\nActive rules / Armed — how many of your alert rules are active, and how many are currently armed to fire on the next valid cross.\n\nLast Telegram fire — age of your most recent delivered (or recorded) fire.\n\nSnapshot age — freshest watchlist or index tick in Postgres. Stale home usually means the poller is idle or nothing is watched — see Health.",
      },
      {
        question: "What are Market indexes and Top movers?",
        answer:
          "Indexes (ASPI, S&P SL20, and friends) come from poller-stored index snapshots. Expand opens a research chart (same family as company candles/ticks) — not a brokerage terminal. Empty path copy means index daily bars are not loaded yet.\n\nTop gainers/losers are the latest snapshot % movers (short list). Same family of data as Browse movers — not a recommendation list.",
      },
      {
        question: "What is the Sectors strip?",
        answer:
          "Session sector board change % as a heat strip on Overview — discovery coloring from stored sector performance, not a tip list or sector allocation advice.",
      },
      {
        question: "What is the XD week strip?",
        answer:
          "Upcoming ex-dividend events on symbols you watch, within about the next week on the Colombo calendar. It is a watchlist reminder strip — not a full dividend calendar product. See Dividends for XD vs payment day.",
      },
    ],
  },
  {
    id: "tape-pulse",
    title: "Tape pulse",
    summary: "Appetite · Foreign net · Book pressure chips.",
    items: [
      {
        question: "What is Tape pulse?",
        answer:
          "A three-chip research strip on Overview and Context: session Market Appetite, Foreign net flow, and public Book pressure. Mood and tape diagnostics — not trading tips. Appetite math is under Market Appetite.",
      },
      {
        question: "How is Foreign net shown?",
        answer:
          "Latest `foreign_net` from market daily summary (LKR). Δ is today − prior session net when both exist. Purchase / sales / turnover can show a foreign activity share when those fields are present.\n\nEmpty foreign chips mean the summary row is missing — not invented zeros.",
      },
      {
        question: "What do Bid heavy / Ask heavy / Balanced mean?",
        answer:
          "koel sums recent order-book bid and ask sizes, then:\n\n• bid_share % = bids / (bids + asks) × 100\n• imbalance % = (bids − asks) / (bids + asks) × 100\n\nLabels: imbalance ≥ +8% → Bid heavy; ≤ −8% → Ask heavy; otherwise Balanced.\n\nExample: bids 60, asks 40 → bid share 60%, imbalance +20% → Bid heavy. Research book snapshot — not a quote to trade against.",
      },
    ],
  },
  {
    id: "market-browse",
    title: "Browse market",
    summary: "Filters, Has EPS, movers, sort, pagination.",
    items: [
      {
        question: "What is Browse showing?",
        answer:
          "One row per CSE symbol from the latest Postgres price snapshot (and name/sector from stocks). The dash never calls the exchange site from the browser — if the table is empty or old, check the poller / Health.",
      },
      {
        question: "How do search, sector chips, and Has EPS work?",
        answer:
          "Search matches symbol or name. Sector chips filter to that exact sector string. Has EPS keeps names with a successful filing_metrics extract and a non-null basic EPS — a research extract filter, not a quality tip.\n\nWhen any of search / sector / Has EPS is on, Browse switches to a filtered table mode: Top movers and the full sector chip cloud hide so the list stays focused.",
      },
      {
        question: "How is the table sorted and paginated?",
        answer:
          "Default sort is change % descending (gainers first). Page size is 50 symbols. An out-of-range page sends you back to page 1. Clear filters if you expected movers and only see the table.",
      },
    ],
  },
  {
    id: "context-macros",
    title: "Context macros",
    summary: "USD/LKR, oil, tourism, food + sector bridges.",
    items: [
      {
        question: "What is Context vs Appetite vs Overview?",
        answer:
          "Overview = your home tape + watchlist slice. Appetite = the 0–100 CSE mood meter. Context = official / attributed macros around the tape (CBSL FX, EIA oil, CBSL tourism earnings, CBSL CCPI food pressure when enabled) plus the same Tape pulse.\n\nContext is research framing — not a macro trading terminal.",
      },
      {
        question: "Where do the macro cards come from?",
        answer:
          "Each card shows a stored series with attribution and as-of date, plus a short history spark. The % badge is change vs the prior point in that stored series.\n\nLive cards come from `macro-tick`: CBSL FX spreadsheet, EIA oil (API or PET bulk zip), CBSL tourism earnings sheet, and CBSL CCPI (food pressure). Direct SLTDA/DCS scrapes stay off (ToS). Old “demo seed” fixture rows are hidden when live rows exist. Empty = ingest off or source down — not a broken quote.",
      },
      {
        question: "What are the sector bridge links?",
        answer:
          "Shortcuts into Browse search (`/market?q=…`) for related CSE names. Discovery helpers only — not “names to buy.” World tiles are research / delayed (FRED + Yahoo, ≤5). News on Context is disclosure-first from CSE filings + notices — no social-feed clone.",
      },
    ],
  },
  {
    id: "people-dossier",
    title: "People & dossiers",
    summary: "Linked influence, seats, network, leadership filter.",
    items: [
      {
        question: "What does Linked influence mean?",
        answer:
          "A research proxy — not personal net worth. For each issuer seat, koel takes role_weight × company market_cap (equity fallback when needed), keeps the max contribution per symbol, then sums across seats.\n\nExample role weights: Chair / CEO / MD = 1.0, Deputy chair = 0.7, Executive director = 0.45, Independent / NED ≈ 0.25, Company secretary = 0.15.\n\nExample: Chair of A (mcap 10B) + NED of B (mcap 2B) → 1.0×10B + 0.25×2B = 10.5B compact LKR label.",
      },
      {
        question: "What are Linked volume and turnover?",
        answer:
          "Sums of the latest issuer session volume / turnover across distinct companies where the person has a seat. That is company tape activity linked to their board map — not evidence of personal trading.",
      },
      {
        question: "What is Leadership vs All on the map?",
        answer:
          "Leadership keeps Chair / CEO / MD-style roles on the people canvas; All shows a broader role set. The canvas ranks by influence and densifies the top of the graph — it is not a complete company registry.",
      },
      {
        question: "What are Seats / Network / Across years?",
        answer:
          "Dossier tabs: Seats = issuers and roles with price/change/volume/mcap/turnover when present. Network = co-directors who share seats. Across years / filings timeline = issuer disclosures around board context.\n\nSoft-merged name variants collapse initials spelling differences; the display name stays the primary CSE string. Board data refreshes when operators run directors-backfill — not a live registry feed.",
      },
      {
        question: "What is Influence share %?",
        answer:
          "On a dossier, each seat’s contribution (mcap × role_weight) as a share of that person’s total linked influence. Bars sum to ~100% for that person.\n\nExample: Chair of A (contrib 10B) + NED of B (0.5B) → about 95% / 5%. Still not personal net worth.",
      },
      {
        question: "What does the Network / ego map show?",
        answer:
          "A small map of the person → their companies (capped) → co-directors who share those boards (capped). Click a company to open the symbol page; click a peer to open their dossier. It is a board-overlap sketch — not a trading network.",
      },
      {
        question: "Is Across years a full career history?",
        answer:
          "No. CSE companyProfile boards are live snapshots, not a historical appointments archive. The timeline mixes board-context events with issuer filings koel stored — Board event vs Filing badges. Gaps mean missing extracts, not “never held a seat.”",
      },
    ],
  },
  {
    id: "ownership-graph",
    title: "Ownership map",
    summary: "PDF-extracted group links, hubs, focus, confidence.",
    items: [
      {
        question: "Where does ownership data come from?",
        answer:
          "Edges parsed from public CSE annual-report PDFs — CSE has no ownership JSON API. koel keeps medium+ confidence edges; low confidence and group-mention noise are dropped. Research map, not a complete register.",
      },
      {
        question: "What do relation colors and Holdings hubs mean?",
        answer:
          "Relations include Subsidiary, Associate, Joint venture, and Related party (legend colors on the canvas).\n\nHoldings hubs (`?hubs=1`) keeps parents of subsidiary/associate edges (and holdings-named listed nodes) plus their children — a denser group map when the full graph is noisy.",
      },
      {
        question: "How does Focus / ?symbol= work?",
        answer:
          "Search or click a node to focus (`?symbol=` on the URL). Blank click clears focus. Company pages’ Ownership map button jumps here with that symbol when supported. Isolated listed nodes usually mean no medium+ PDF edge yet — missing data, not proof of “no subsidiaries forever.”",
      },
    ],
  },
  {
    id: "alert-history",
    title: "Alert history",
    summary: "Sent, retrying, dead-lettered, filters, pages.",
    items: [
      {
        question: "History vs Alerts?",
        answer:
          "Alerts = your active rules. History = the audit trail of fires from Postgres when rules matched (Telegram is still the push path). Re-arm-only events do not create user-facing history rows.",
      },
      {
        question: "What do Sent / Delivered / Retrying / Dead-lettered mean?",
        answer:
          "Sent — Telegram delivery recorded.\n\nDelivered (unmarked) — Telegram accepted the message but the durable sent flag is missing.\n\nRetrying — koel is still attempting delivery (attempt count may show).\n\nDead-lettered — retries stopped; the fire will not keep trying automatically.",
      },
      {
        question: "How do filters and pages work?",
        answer:
          "Filter by symbol; choose a page size (about 25–200). Changing the symbol filter resets you to the first page. Empty history means no fires yet — not that rules are broken.",
      },
    ],
  },
  {
    id: "settings",
    title: "Settings",
    summary: "Digest, quiet hours, quota, log out vs all devices.",
    items: [
      {
        question: "What does Digest mode do?",
        answer:
          "When digest is on, koel can batch eligible overnight activity into a digest instead of a stream of immediate pings. Actionable session fires still prefer Telegram push when outside quiet-hour hold logic. Exact batching follows your deployment’s digest support.",
      },
      {
        question: "How do quiet hours work?",
        answer:
          "Start and end hours in Asia/Colombo. Set both, or leave both Off. Overnight windows are OK (e.g. 22 → 06). Same start and end turns quiet hours off.\n\nDuring quiet hours, pushes are held then delivered later — not silently dropped.",
      },
      {
        question: "What is alert quota?",
        answer:
          "A read-only cap on how many active rules you can keep. Creating beyond the limit fails at the API. Cancel unused rules if you hit the ceiling.",
      },
      {
        question: "Log out vs All devices?",
        answer:
          "Open the account chip (your Telegram id) in the top bar for both. Log out ends this browser session only. All devices calls logout-all and revokes every recorded dash session for your account. Use All devices if a shared or lost device still has access.",
      },
    ],
  },
  {
    id: "watchlist",
    title: "Watchlist",
    summary: "Columns, refresh, unknown symbols, Telegram sync.",
    items: [
      {
        question: "What does the Watchlist table show?",
        answer:
          "Symbols you follow with latest stored price, change %, and updated time. Unwatch removes the row. The soft refresh chip ages the freshest snapshot on the list.\n\nPushes still need alert rules — watching alone does not Telegram every tick.",
      },
      {
        question: "Why can’t I add a symbol?",
        answer:
          "Add rejects tickers missing from the stocks table (“Unknown symbol”). Browse after a poll, use Telegram `/watch SYMBOL`, or wait until the poller has seen the name. Dash and bot share one watchlist store.",
      },
    ],
  },

  {
    id: "alerts",
    title: "How alerts work",
    summary: "Crossing, armed / re-arm, daily limits, mute, quiet hours.",
    items: [
      {
        question: "Do price alerts fire if the price is already past my level?",
        answer:
          "No — price above/below rules fire on a cross (transition), not on “currently above.”\n\nExample: rule “above 100.” Price path 99 → 100.5 fires once. If you create the rule while price is already 105, it does not fire until price goes below 100 and later crosses back up through 100.",
      },
      {
        question: "What does Armed mean?",
        answer:
          "Armed means the rule is ready to fire on the next valid cross. After a price above/below fire, koel disarms the rule so it does not spam every tick while price stays on that side.\n\nIt re-arms when price moves back to the other side of the threshold (a silent “rearm” event — not a Telegram push).",
      },
      {
        question: "How does Daily move work?",
        answer:
          "Daily move fires when the absolute daily % move (|change %|) reaches or crosses your threshold. koel uses CSE change % when present, otherwise derives % from previous close.\n\nAt most one fire per Colombo calendar day per rule (not UTC midnight).\n\nExample: threshold 5 — a day that goes +5.2% or −5.2% can fire once that Colombo day.",
      },
      {
        question: "When do disclosure alerts fire?",
        answer:
          "Only for filings koel sees with a published time at or after you created the rule — older archive rows do not back-fire. Filings missing a usable published time do not fire.\n\nOptional category filters narrow which announcement types count. You need an explicit disclosure rule; watching a symbol alone does not push every filing.",
      },
      {
        question: "Mute, quiet hours, digest, quota?",
        answer:
          "Mute pauses Telegram fires for one rule until a time you set. Quiet hours (Settings) hold pushes overnight in Asia/Colombo and can deliver a digest instead. Digest batches overnight activity.\n\nAlert quota caps how many active rules you can keep — Settings shows your limit. See Settings and Alert history for delivery detail.",
      },

      {
        question: "What does Mute 24h / Clear mute do?",
        answer:
          "Mute 24h sets muted_until about a day ahead for that rule — Telegram fires pause until then (or until you Clear mute). The row shows a muted badge with the until time. Mute does not cancel the rule or change Armed.",
      },
      {
        question: "What does Test fire do?",
        answer:
          "Creates a dry-run style audit check from the dash so you can confirm wiring. It does not send a live Telegram push and does not mean the market crossed your level.",
      },
      {
        question: "What does Cancel do vs Armed?",
        answer:
          "Cancel deactivates the rule (leaves the active list). Armed / disarmed is separate: after a price cross fire the rule disarms until price re-arms on the other side. Cancelled rules do not fire; disarmed active rules still exist and can re-arm.",
      },
      {
        question: "Why is Symbol locked to MARKET?",
        answer:
          "Some rule types are market-wide: halt, Market Appetite, foreign flow, book pressure, USD/LKR move, oil move, and XD digest. The create form forces Symbol to MARKET for those (same as bot `/alert MARKET …`). Per-symbol types still need a real CSE ticker.",
      },
      {
        question: "What do the threshold fields mean on the create form?",
        answer:
          "Labels change with type:\n\n• Price — LKR level for above/below crosses\n• Percent — daily |%| move, gap %, or YoY %\n• Multiplier — volume spike / up / down / crossing (e.g. 2 → ≥ 2× recent average)\n• Shares — big print size\n• Appetite score ≥ — MARKET minimum 0–100 score\n• Foreign net (LKR) — absolute foreign_net magnitude\n• Days — XD soon / digest horizon\n\nBuy-in, non-compliance, halt, share split / consolidation, and plain disclosure need no numeric threshold (disclosure may take an optional category).",
      },
      {
        question: "How does the disclosure Category field work?",
        answer:
          "Optional. Blank = any new filing after the rule was created. Set = disclosure.category must contain your text (case-insensitive substring), e.g. Financial.\n\nThat is not the same as the category chips on a company page (those only filter the timeline view).",
      },
      {
        question: "Why don’t filing EPS / YoY alerts fire yet?",
        answer:
          "Those rules need financial-metrics extract flags enabled in the deployment (FINANCIAL_METRICS / YOY_COMPARE). When flags are off, koel may still shadow-log matches without sending Telegram. Check Health / ops config if the dash form warns about metrics flags.",
      },
      {
        question: "Can I set the same alerts in Telegram?",
        answer:
          "Yes. Bot commands mirror the dash for core types — e.g. /alert JKH.N0000 above 200, /alert JKH.N0000 move 5, /alert JKH.N0000 disclosure. Full command list: /help in Telegram. See also the Telegram topic below.",
      },
    ],
  },
  {
    id: "alert-types",
    title: "Alert types & examples",
    summary: "What each rule type measures and a concrete example.",
    items: [
      {
        question: "Above / Below (price cross)",
        answer:
          "Fires when last price crosses your level from the other side (see Armed).\n\nExample: Below 45 on ABC.N0000 — path 45.20 → 44.90 fires; staying at 44.50 does not re-fire until re-armed above 45.",
      },
      {
        question: "Daily move",
        answer:
          "|change %| vs previous close reaches your percent threshold; one fire per Colombo day.\n\nExample: move 3 on LOLC.N0000 when the day is +3.1% or −3.1%.",
      },
      {
        question: "Disclosure",
        answer:
          "New CSE announcement for the symbol after the rule was created (optional category).\n\nExample: disclosure on COMB.N0000 with category filter for financial results.",
      },
      {
        question: "Volume spike / up / down",
        answer:
          "Current volume ≥ your multiple × recent average volume. Volume up/down also care about price direction that day.\n\nExample: volume spike 3 — today’s volume at least 3× the recent average.",
      },
      {
        question: "Crossing volume & big print",
        answer:
          "Crossing volume: notable volume threshold crossed for the symbol. Big print: a single trade/print size at or above your share count.\n\nThese are activity signals from stored trade/volume fields — not a recommendation to trade.",
      },
      {
        question: "Gap",
        answer:
          "Fires when |open − previous_close| / previous_close × 100 reaches your percent.\n\nExample: gap 2 — open is at least 2% away from prior close.",
      },
      {
        question: "Share split / consolidation",
        answer:
          "No threshold. Fires when koel sees a near-integer session price cliff (about ×2 / ×3 / ×4 / ×5 / ×8 / ×10 forward or reverse vs the prior koel snapshot — not the exchange previous-close field, which is often already reset on subdivision day) or when a CSE filing matches subdivision / share-split / consolidation wording.\n\nOne price-path fire per Colombo day; disclosure fires are keyed per filing. Example: `/alert JINS.N0000 split`. Heuristic — confirm against the CSE announcement. Watching alone still does not ping.",
      },
      {
        question: "Buy-in, non-compliance, halt",
        answer:
          "Notice-board style rules. Buy-in and non-compliance are per symbol; halt can be market-wide (MARKET).\n\nThey fire when koel ingests matching CSE notices — informational only.",
      },
      {
        question: "Bid-heavy / ask-heavy book",
        answer:
          "Order-book pressure heuristics: bid side (or ask side) looks heavy vs your threshold multiple.\n\nExample: bidheavy 2 — bid interest at least about 2× the ask side by koel’s stored book snapshot.",
      },
      {
        question: "EPS / revenue / profit YoY filing metrics",
        answer:
          "Optional rules that compare extracted filing metrics (EPS, revenue YoY, profit YoY) to a threshold. Live fire needs metrics flags enabled in the deployment.\n\nExample: “EPS YoY above 10” when a filing’s extracted YoY EPS % clears +10.",
      },
      {
        question: "Market Appetite, foreign flow, book pressure, USD/LKR, oil",
        answer:
          "Regime-style MARKET rules — the create form locks Symbol to MARKET.\n\nMarket Appetite is a minimum score threshold, not a band picker: it fires when the composite score is ≥ your number (e.g. threshold 61 ≈ the Appetite band floor). Foreign flow uses |foreign_net| in LKR vs your threshold. Book pressure uses |imbalance %| vs your threshold. USD/LKR and oil use stored macro move thresholds.\n\nExample: Appetite score ≥ 61 on MARKET when the meter prints 63.",
      },
      {
        question: "XD soon / XD digest",
        answer:
          "XD soon (per symbol): Days = horizon. Fires when an stored XD date falls within that many Colombo days — once per (rule, XD date), not every poll.\n\nXD digest is MARKET + watchlist-scoped: a weekly digest of upcoming XDs on names you watch (once per ISO week per rule), not a daily ping.\n\nExample: `/alert JKH.N0000 xd 7` vs `/alert MARKET xd_digest 7`. Always verify the CSE announcement before acting on dates.",
      },
    ],
  },
  {
    id: "signals",
    title: "Signal Board",
    summary: "Research scores (−100…100), reasons, Spoke vs Silent.",
    items: [
      {
        question: "What is a research score?",
        answer:
          "A transparent composite from daily path data (and optional filing / peer / notice factors), clamped to about −100…100. Model version labels like path_v5 tell you which factor set was used.\n\nHigher score ≠ buy. Lower score ≠ sell. Scores are research diagnostics with explainable reason lines — never “best to invest” language.",
      },
      {
        question: "How is the score calculated (path_v5 gist)?",
        answer:
          "Needs at least 5 daily bars. Momentum blends 5-day, 20-day, and 60-day returns (roughly 40 / 35 / 25 weight). koel subtracts a volatility penalty, then adds smaller terms for liquidity, volume regime, turnover, filing YoY / disclosure activity, sector relative strength, notices, and rank stability when those inputs exist.\n\nThe raw sum is clamped to [−100, 100]. Missing optional factors simply contribute zero — they do not invent data.",
      },
      {
        question: "What are reasons and rank Δ?",
        answer:
          "Reasons are short, guardrailed explanations of the largest factor contributions (safe wording only).\n\nRank is position on the board that day; rank Δ is change vs the prior board date (positive = moved up the list). Rank moves are not tips.",
      },
      {
        question: "Spoke vs Silent / forecast gates?",
        answer:
          "Spoke means a selective forecast overlay cleared koel’s gates for that row. Silent means no selective forecast is shown — the research score can still appear.\n\nGates are quality filters, not buy/sell calls. Confidence bands describe model self-checks, not guaranteed outcomes. See Forecast overlay for Selective ~90% / ~73% / LTR labels.",
      },
      {
        question: "What is on each Signal Board row?",
        answer:
          "Rank # and rank Δ, symbol, Spoke/Silent, optional gate label + confidence, reason bullets, model version · as-of · bar count · prior rank, and the score (−100…100).\n\nRank Δ needs a prior board date: ↑N / ↓N vs prior rank, new when the name was absent before, or — when Δ is unavailable.",
      },
      {
        question: "What is Spoke coverage on the page?",
        answer:
          "A count of how many loaded rows are Spoke vs Silent (board load is capped). Selective coverage is a research filter rate — not a hit-rate promise for tomorrow. Empty board usually means path backfill / score-signals has not landed yet. A 1–2 row board after a smoke run is skipped automatically — the dash prefers the latest dense tip day.",
      },
    ],
  },
  {
    id: "appetite",
    title: "Market Appetite",
    summary: "0–100 session mood proxy and band labels.",
    items: [
      {
        question: "What does Appetite measure?",
        answer:
          "A daily research composite (0–100) for how “risk-on” the CSE tape looks from breadth, move intensity, ASPI day change, and participation. It is a mood proxy — not a recommendation to buy or sell anything.",
      },
      {
        question: "How is the score calculated?",
        answer:
          "Weighted blend of four 0–100 component scores:\n\n• Breadth 40% — share of names with positive daily change %\n• Intensity 25% — among names moving at least ~2%, share that are up\n• Index 20% — ASPI daily change % mapped so about −3% → 0, 0% → 50, +3% → 100\n• Participation 15% — turnover/volume participation vs recent history (z-score style), with simpler fallbacks when history is thin\n\nExample: breadth 60, intensity 55, index 50, participation 40 → 0.40×60 + 0.25×55 + 0.20×50 + 0.15×40 = 53.75.",
      },
      {
        question: "What do the bands mean?",
        answer:
          "Bands are labels on the 0–100 score:\n\n• under 20 — extreme caution\n• 20–40 — caution\n• 40–60 — neutral\n• 60–80 — appetite\n• 80+ — strong appetite\n\nLabels describe the meter, not what you should trade.",
      },
      {
        question: "CSE vs hybrid research series?",
        answer:
          "History chips: shorter ranges (about 3M / 1Y) prefer CSE-truth daily scores. Longer ranges (5Y / MAX) may use a Yahoo+CSE hybrid research series (often with an amber notice). Long windows can weekly/monthly average so the chart stays readable.\n\nTreat hybrid as research context; headline session mood prefers CSE-backed days when available.",
      },
      {
        question: "Why was the newest thin day skipped for the headline?",
        answer:
          "When the newest appetite day has a tiny universe (under about 100 names with computable changes), koel can skip it for the big headline number and show the last fuller board day instead. The thin day may still appear as a hollow tip on the history chart.\n\nThe Universe KPI is that `universe_n` count (sometimes with advancers↑ / decliners↓) — the same figure used for thin-day skip.",
      },
      {
        question: "What are Δ 1 / 5 / ~1 month and Days in band?",
        answer:
          "Δ values are score-point differences vs about 1 / 5 / ~22 sessions earlier — not percent moves. Days in band counts how many consecutive sessions backward share the same band label (caution, neutral, appetite, …).",
      },
      {
        question: "What do Components and Band chronology show?",
        answer:
          "Components bars break the headline into breadth / intensity / index / participation (the same 40/25/20/15 mix). Band chronology (tracker) walks recent days’ band labels so you can see how long the meter has sat in a mood — still not a tip.",
      },
    ],
  },
  {
    id: "disclosures",
    title: "Disclosures & briefs",
    summary: "Filings, PDFs, categories, and AI brief status.",
    items: [
      {
        question: "Where do disclosures come from?",
        answer:
          "CSE announcement JSON the poller stores (preferred: per-company feed for watchlist symbols; also market-wide approved announcements). Titles, URLs/PDFs, and published times are what koel shows on symbol pages and in alert pushes. Title links go to a safe PDF or announcement URL when koel has one.",
      },
      {
        question: "What about AI briefs?",
        answer:
          "Some deployments attach a short filing brief. On the company page, a ready brief can appear in Latest brief and under timeline rows; · processing means the drain is still working. Live AI generation is flag- and key-gated and may be off by default.\n\nA missing brief is normal — the source PDF/link remains the authority. See also Filing metrics.",
      },
      {
        question: "What do disclosure category chips on a company page do?",
        answer:
          "They filter the timeline of stored filings for that page (`?category=`). That is a view filter only — not the same as setting a category on a disclosure alert rule (which controls which new filings can fire Telegram).",
      },
      {
        question: "Category filters on disclosure alerts?",
        answer:
          "When you set a category on an alert rule, only matching announcement types fire that rule. Leave category empty to listen for any new filing after rule create (still subject to published-time rules under How alerts work).",
      },
    ],
  },
  {
    id: "dividends",
    title: "Dividends",
    summary: "XD timing, event yield on symbols, session-only cash estimate.",
    items: [
      {
        question: "How does the dividend calculator work?",
        answer:
          "Estimate ≈ DPS × shares, with an optional rough withholding-tax (WHT) haircut. Share quantities stay in the browser session only — koel does not store a portfolio or cost basis here.\n\nExample: DPS 1.50, 1,000 shares → 1,500 before WHT estimate.",
      },
      {
        question: "What is Event yield on a company page?",
        answer:
          "When koel has a latest dividend event with DPS and a last price, Event yield ≈ DPS ÷ last price × 100. That is a single-event research label — not a trailing twelve-month yield.\n\nExample: DPS 2.00 on price 50.00 → 4.00%. The strip also shows XD / Pay when those dates were parsed from CSE dividend disclosures.",
      },
      {
        question: "How do multi-row rows and the 14% WHT checkbox work?",
        answer:
          "The calculator keeps session-only symbol rows (add several names). Each row has Shares and DPS; cash ≈ DPS × shares. Combined cash sums the rows.\n\nApply WHT (14%) estimates net = gross × (1 − 0.14). Example: DPS 1.50 × 1,000 = 1,500 gross → WHT 210 → net 1,290. This is a rough research estimate — not a tax report or WHT certificate.",
      },
      {
        question: "XD vs payment day?",
        answer:
          "Ex-dividend (XD) day: new buyers typically do not receive that dividend; the stock usually still trades. Payment day is when cash is scheduled — not a market holiday.\n\nDates come from CSE dividend disclosures koel stored. If a filing says “dates to be notified,” koel shows that honestly until a later filing fills them in. You can also set XD soon / XD digest alerts.",
      },
    ],
  },
  {
    id: "people-graph",
    title: "People & ownership hub",
    summary: "Where to go for dossiers vs ownership edges.",
    items: [
      {
        question: "People vs Ownership map?",
        answer:
          "People ranks directors/officers by linked influence and opens dossiers (seats, network, filings). Ownership map draws company-to-company edges from annual-report PDF extracts.\n\nSee People & dossiers and Ownership map for field-level explainers. Neither is a live company registry.",
      },
      {
        question: "How do I open ownership from a company page?",
        answer:
          "Use Ownership map (jumps to Graph focused on that symbol when supported) or People. The company page itself does not embed a full ownership table.",
      },
      {
        question: "Why might a person or edge be missing?",
        answer:
          "Coverage follows what koel has stored from CSE companyProfile boards and PDF extracts. Incomplete filings, name-matching limits, or not-yet-ingested rows all mean gaps. Treat absences as missing data, not as “no relationship.”",
      },
    ],
  },
  {
    id: "health",
    title: "Health & the poller",
    summary: "Market hours, freshness, and what Health reports.",
    items: [
      {
        question: "When does the poller run?",
        answer:
          "During CSE market hours: about 09:30–14:30 Asia/Colombo on weekdays. Outside that window the poller idles. Operators can force a tick with the backend `tick --force` command; the dash never scrapes CSE itself.",
      },
      {
        question: "What should I look at on Health?",
        answer:
          "Poller / snapshot freshness, recent errors, and related ops signals (including ML health when present). If Overview looks empty after a holiday weekend, confirm the next session has produced new snapshots.",
      },
      {
        question: "Near-realtime — how fresh is “fresh”?",
        answer:
          "koel is poll-interval near-realtime, not exchange co-lo. Expect updates on the order of the poller interval during the session, then quiet after the close until the next open (unless someone forces a tick).",
      },
      {
        question: "Snapshot age vs tick age?",
        answer:
          "Snapshot age = last price_snapshots write in Postgres (what the dash reads). Tick age = last poller loop heartbeat via HEALTH_URL on a host that can reach the poller — often absent on Vercel-only deploys. Missing poller detail is an ops wiring gap, not proof snapshots stopped.",
      },
      {
        question: "What is Data inventory / CI / ML / delivery?",
        answer:
          "Data inventory — Postgres counts (stocks, snapshots, disclosures, metrics, briefs, alerts, watchlist) plus migration / appetite / live macro tips (USD/LKR + Brent as-of).\n\nGitHub Actions — latest workflow runs (≤~60s cache) and a scheduled-job checklist matched to that strip (not a separate cron API). ✓ success/in-progress · ! skipped/failed · — not in the recent window.\n\nModel / forecast — serving champion, gated hit-rate style stats, spoke coverage, related research ops (not tips).\n\nTelegram delivery — delivered (24h) / retrying / dead-lettered from alert_log.\n\nFull ops blocks may require your Telegram id on DASH_OPS_TELEGRAM_IDS.",
      },
      {
        question: "Watched missing, circuits, brief queue, retention?",
        answer:
          "Watched missing — watched symbols absent from the latest trade summary.\n\nCircuits — adapter breaker state after CSE failures.\n\nBrief queue — pending AI briefs / PDF enrich.\n\nRetention — SNAPSHOT_RETENTION_DAYS (0 keeps all). These are ops diagnostics for why the tape looks thin.",
      },
    ],
  },
  {
    id: "telegram",
    title: "Telegram commands",
    summary: "Parity with the bot /help surface.",
    items: [
      {
        question: "Core commands",
        answer:
          "/start — register and short explainer\n/watch SYMBOL — add to watchlist\n/unwatch SYMBOL — remove\n/alert SYMBOL above|below PRICE — price cross\n/alert SYMBOL move PERCENT — daily |%| move\n/alert SYMBOL disclosure — new filings\n/alert SYMBOL split — share split / consolidation\n/myalerts — list rules\n/mywatchlist — list watchlist\n\nMore activity and notice types share the same /alert family; the bot /help lists the full syntax. Dash and bot share one rule store.",
      },
      {
        question: "Will every dash alert push to Telegram?",
        answer:
          "Active, unmuted rules fire to Telegram when conditions match, subject to quiet hours, digest, and mute. Rearm-only events do not send a push. History in the dash shows what already fired.",
      },
      {
        question: "How do I cancel a rule from Telegram?",
        answer:
          "Use `/cancel ALERT_ID` with the numeric id from `/myalerts` — same cancel as the dash Cancel button. If you hit a command rate-limit reply, wait a moment and retry.",
      },
      {
        question: "What is /brief SYMBOL?",
        answer:
          "Read-only: shows the latest ready AI filing brief koel stored for that symbol. You may see “none yet” (no ready brief) or that AI briefs are off for the deployment. Source PDF/link remains the authority — see Filing metrics & briefs.",
      },
    ],
  },
  {
    id: "nfa",
    title: "Not financial advice",
    summary: "Compliance framing for every price- and score-adjacent view.",
    items: [
      {
        question: "Is koel investment advice?",
        answer:
          "No. koel is an information tool. Prices, scores, appetite bands, briefs, and alerts are not invitations to deal in securities and are not recommendations.\n\nCopy matches the spirit of SEC Sri Lanka Part V market-misconduct themes: do not treat koel as inducing dealing or as a source of insider information. Always verify primary CSE disclosures before acting.",
      },
      {
        question: "What koel deliberately does not do (yet)",
        answer:
          "No portfolio quantities / cost basis / P&L tracker, no tax reports, no heavy multi-filter trading terminal, no full TA suite, no native mobile app, and no payments. If a feature is not about seeing the market in the dash or getting pinged on Telegram, it is out of scope for now.",
      },
      {
        question: "What is Scenarios?",
        answer:
          "A Phase 3 stub (deep-link `/scenarios`, off primary nav). Even when AI_SCENARIOS_ENABLED is on, the dash does not run AgentChat, personas, or model calls yet. Alerts stay on Telegram; this page is only an informational fence.",
      },
    ],
  },
] as const;

/** Lookup a topic by hash id (without leading #). */
export function getHelpTopic(id: string): HelpTopic | undefined {
  if (typeof id !== "string" || !id) return undefined;
  return HELP_TOPICS.find((t) => t.id === id);
}

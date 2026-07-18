# Quiverly brand assets

Product name in prose/UI: **Quiverly**. Wordmark: lowercase **quiverly**. Mark: capital **Q**.

- `quiverly-logo.svg` — full lowercase wordmark (square master)
- `quiverly-mark.svg` — standalone **Q** mark (favicon, app icon, avatar)
- `quiverly-logo-tight.svg` / `quiverly-mark-tight.svg` — tight `viewBox` for UI chrome

Ink color in the paths is `#1e1e1e` — keep dash/marketing paper light so the mark stays readable.

**Web runtime copies** live under `web/public/brand/` and use the **tight** crop so nav/hero
wordmarks are not drowned in empty square padding. Prefer `/brand/quiverly-logo.svg` via
`QuiverlyWordmark` / `QuiverlyMark` in `web/src/components/brand/quiverly-brand.tsx`.

Legacy `chime-*` files in this folder remain as archives; do not use them for product chrome.

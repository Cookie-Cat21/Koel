# Quiverly brand assets

Product name in prose/UI: **Quiverly**. Wordmark: lowercase **quiverly**. Mark: capital **Q**.

- `quiverly-logo.svg` — full lowercase wordmark (square master)
- `quiverly-mark.svg` — geometric capital **Q** (thick ring + block foot; favicon / avatar)
- `quiverly-logo-tight.svg` / `quiverly-mark-tight.svg` — tight `viewBox` for UI chrome

Ink color in the paths is `#1e1e1e` — keep dash/marketing paper light so the mark stays readable.

**Web runtime copies** live under `web/public/brand/` and use the **tight** crop so nav/hero
wordmarks are not drowned in empty square padding. Prefer `/brand/quiverly-logo.svg` via
`QuiverlyWordmark` / `QuiverlyMark` in `web/src/components/brand/quiverly-brand.tsx`.

If you have newer master SVGs from design, replace `quiverly-logo.svg` / `quiverly-mark.svg`
here first, regenerate the `-tight` crops into `web/public/brand/`, then refresh the PNG/ICO
favicon set from the mark (~70–75% fill).

Legacy `chime-*` files in this folder remain as archives; do not use them for product chrome.

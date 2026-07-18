# koel brand assets

Product name in prose/UI: **koel** (lowercase). Wordmark: lowercase **koel**. Mark: capital **K**.

- `koel-logo.svg` — full lowercase wordmark (square master on black)
- `koel-mark.svg` — geometric capital **K** (favicon / avatar)

Ink color in the paths is `#262626` — charcoal on black for masters; UI crops under
`web/public/brand/` use the same ink on transparent so the mark stays readable on
the light dash/marketing paper.

**Web runtime copies** live under `web/public/brand/`. Prefer `/brand/koel-logo.svg`
via `KoelWordmark` / `KoelMark` in `web/src/components/brand/koel-brand.tsx`.

Legacy `quiverly-*` / `chime-*` files in this folder (if present) are archives only.

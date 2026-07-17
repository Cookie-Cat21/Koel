# Apply Market module to ArdenoStudio/ceyfi

This Cloud Agent cannot push to `ArdenoStudio/ceyfi` (403). Apply locally:

```bash
git clone https://github.com/ArdenoStudio/ceyfi.git
cd ceyfi
git checkout -b cursor/market-chime-module-9a91
git apply /path/to/Chime/docs/factory/ceyfi-market-port/0001-market-chime-module.patch
# or copy from files/ over the repo root
git add -A && git commit -m "Add Market module powered by Chime"
git push -u origin cursor/market-chime-module-9a91
```

Then open a PR on Ceyfi. Optional live proxy: set `CHIME_API_BASE` on the Ceyfi backend.

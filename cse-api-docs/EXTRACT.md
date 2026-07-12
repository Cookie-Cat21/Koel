# Extract to a standalone GitHub repository

This tree is staged inside [Chime](https://github.com/Cookie-Cat21/Chime) because the
cloud agent token cannot `gh repo create`. To publish as its own project:

```bash
# from a machine with repo-create rights
gh repo create Cookie-Cat21/cse-api-docs --public --description "Unofficial CSE (cse.lk) API docs — live-probed"
git clone https://github.com/Cookie-Cat21/cse-api-docs.git
cd cse-api-docs
# copy contents of this folder (except nothing nested under Chime)
rsync -a --exclude site/ ../Chime/cse-api-docs/ ./
# or: git subtree split -P cse-api-docs -b cse-api-docs-split
python3 scripts/probe.py && python3 scripts/build_site.py
git add -A && git commit -m "Initial unofficial CSE API docs"
git push -u origin main
# Enable GitHub Pages from /site or docs workflow
```

Until then, browse the built site from this monorepo path and the Pages workflow
that publishes `cse-api-docs/site`.

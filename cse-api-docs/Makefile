.PHONY: probe site examples clean

probe:
	python3 scripts/probe.py

site: probe
	python3 scripts/build_site.py

site-only:
	python3 scripts/build_site.py

examples:
	python3 examples/python/quote.py
	python3 examples/python/trade_summary.py

clean:
	rm -rf samples/*.json catalog/last_probe.json catalog/PROBE_REPORT.md site

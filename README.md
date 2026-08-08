# Yao GEO

**Version 0.1.0 · Experimental**

Yao GEO is a protocol-first toolkit for turning GEO work into auditable, reusable runs. The current vertical slice includes a registry-driven router, an Artifact Bus, deterministic discovery, evidence-lined diagnosis, JSON Schema contracts, and three active skills.

## Current scope

- `geo`: routes Chinese and English requests through the registry and reports unavailable routes honestly.
- `geo-discover`: converts a validated GEO brief into a deterministic query map, opportunity map, evidence ledger, run manifest, and quality report.
- `geo-diagnose`: evaluates explicit brand, site, or page sources and emits a structured diagnosis, deterministic report, evidence ledger, remediation query map, opportunity map, quality report, and run manifest.
- `geo-content`: reserved as pending implementation for the next main-flow slice.
- strategy, knowledge, publish, and measure: visible roadmap routes with `planned` status.

No connector, platform sampling, search volume, ranking, or conversion data is inferred. Missing evidence remains explicit in generated artifacts.

## Quick start

Requires Python 3.11 or newer.

```bash
python3 -m pip install -e '.[dev]'
python3 -m yao_geo route --text "帮我挖掘 AI 搜索问题"
python3 -m yao_geo discover --input tests/fixtures/brief.json --output runs
python3 -m yao_geo diagnose --input tests/fixtures/diagnosis-page.json --output runs
make verify
```

The CLI prints JSON. The `--output` value is a runs root; discover and diagnose write protocol `1.0.0` runs to `<output>/<run-id>/` and return that actual run directory. Diagnose fetches only explicit public HTTP(S) canonical URLs without query strings, accepts HTML/XHTML, performs no crawl expansion, and snapshots successful pages for offline replay. Unavailable or unsupported sources remain gaps. Its scores do not represent live AI-platform recall, ranking, or citation share.

## License and governance

The open-source repository is licensed under `AGPL-3.0-only`. Commercial licensing is currently `inquiry_only`; see `COMMERCIAL-LICENSING.md`. The contributor agreement remains under legal review, so external code merges are paused.

Copyright © 2026 姚金刚 / Yao.

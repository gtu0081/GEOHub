# Yao GEO

**Version 0.1.0 · Experimental**

Yao GEO is a protocol-first toolkit for turning GEO work into auditable, reusable runs. This first vertical slice includes a registry-driven router, an Artifact Bus, deterministic discovery, JSON Schema contracts, and the `geo` and `geo-discover` skills.

## Current scope

- `geo`: routes Chinese and English requests through the registry and reports unavailable routes honestly.
- `geo-discover`: converts a validated GEO brief into a deterministic query map, opportunity map, evidence ledger, run manifest, and quality report.
- `geo-diagnose` and `geo-content`: reserved as pending implementations for the next main-flow slice.
- strategy, knowledge, publish, and measure: visible roadmap routes with `planned` status.

No connector, platform sampling, search volume, ranking, or conversion data is inferred. Missing evidence remains explicit in generated artifacts.

## Quick start

Requires Python 3.11 or newer.

```bash
python3 -m pip install -e '.[dev]'
python3 -m yao_geo route --text "帮我挖掘 AI 搜索问题"
python3 -m yao_geo discover --input tests/fixtures/brief.json --output runs/demo
make verify
```

The CLI prints JSON. A discover run writes protocol `1.0.0` artifacts under the requested output directory.

## License and governance

The open-source repository is licensed under `AGPL-3.0-only`. Commercial licensing is currently `inquiry_only`; see `COMMERCIAL-LICENSING.md`. The contributor agreement remains under legal review, so external code merges are paused.

Copyright © 2026 姚金刚 / Yao.

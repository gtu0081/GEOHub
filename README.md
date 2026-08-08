# Yao GEO

**Version 0.1.0 · Experimental**

Yao GEO is a protocol-first toolkit for turning GEO work into auditable, reusable runs. The current vertical slice includes a registry-driven router, an Artifact Bus, deterministic discovery, evidence-lined diagnosis, offline content production, JSON Schema contracts, and four active skills.

The skills are Library-engineered packages while product behavior remains **Experimental**. `maturity_tier=library` describes packaging rigor and does not claim production outcome quality.

## Current scope

- `geo`: routes Chinese and English requests through the registry and reports unavailable routes honestly.
- `geo-discover`: converts a validated GEO brief into a deterministic query map, opportunity map, evidence ledger, run manifest, and quality report.
- `geo-diagnose`: evaluates explicit brand, site, or page sources and emits a structured diagnosis, deterministic report, evidence ledger, remediation query map, opportunity map, quality report, and run manifest.
- `geo-content`: creates evidence-lined titles, explainers, comparisons, rankings, page blueprints, refinements, and article-friendly artifacts as JSON, Markdown, and standalone HTML; DOCX/PDF are optional render layers.
- strategy, knowledge, publish, and measure: visible roadmap routes with `planned` status.

The resolver keeps single-intent routing minimal and exposes two exact multi-stage DAGs: `brand-baseline-lite` (discover → diagnose) and `content-campaign` (discover → content). A planned route is never executed; it returns the closest active suggestion, required inputs, and closest v0 artifact. See `skills/RESOLVER.md` and `docs/architecture.md`.

No connector, platform sampling, search volume, ranking, or conversion data is inferred. Missing evidence remains explicit in generated artifacts.

## Quick start

Supported Python range: 3.11-3.14.

```bash
python3 -m pip install -e '.[dev]'
python3 -m yao_geo route --text "帮我挖掘 AI 搜索问题"
python3 -m yao_geo discover --input tests/fixtures/brief.json --output runs
python3 -m yao_geo diagnose --input tests/fixtures/diagnosis-page.json --output runs
python3 -m yao_geo content --input skills/geo-content/references/input-example.json --output runs
make verify
```

Community packages:

```bash
python3 scripts/package.py --target all --channel community
python3 scripts/verify_packages.py
python3 scripts/install_simulation.py --target all
```

The eight artifacts are a source ZIP, one unified single-Skill ZIP, four provider Skill ZIPs, and Codex/Claude adapter ZIPs. Each ZIP supports `pip install .` from its extraction root. Unified and target adapters contain four parseable provider entries and wrappers. Every community artifact is `AGPL-3.0-only`; commercial metadata remains `inquiry_only`. See `docs/installation.md`.

The CLI prints JSON. The `--output` value is a runs root; discover, diagnose, and content write protocol `1.0.0` runs to `<output>/<run-id>/` and return that actual run directory. Content runs never access the network, snapshot relative source files for offline replay, escape user text in standalone HTML, and keep optional renderer failures explicit. If DOCX/PDF dependencies are missing, core output succeeds and the run manifest records `degraded` plus `missing_dependencies`. Install `.[render]` to request DOCX/PDF support. Diagnose fetches only explicit public HTTP(S) canonical URLs without query strings, accepts HTML/XHTML, performs no crawl expansion, and snapshots successful pages for offline replay. Unavailable or unsupported sources remain gaps. Its scores do not represent live AI-platform recall, ranking, or citation share.

## License and governance

The open-source repository is licensed under `AGPL-3.0-only`. Commercial licensing is currently `inquiry_only`; see `COMMERCIAL-LICENSING.md`. The contributor agreement remains under legal review, so external code merges are paused.

Development gates are `make test`, `make eval`, `make verify`, `make package-verify`, `make install-smoke`, or the sequential `python3 scripts/verify_all.py`. They use synthetic fixtures and no external service or secret.

Copyright © 2026 姚金刚 / Yao.

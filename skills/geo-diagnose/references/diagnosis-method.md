# Diagnosis Method

## Diagnosis brief

The JSON object requires `subject` and `scope`, where scope is `brand`, `site`, or `page`. It accepts `target_urls`, `source_html`, `evidence`, `locale`, `audience`, and `goals`. Supply at least one target URL, HTML source, or evidence record. All strings must contain non-whitespace text. Evidence records contain unique `evidence_id`, `claim`, and absolute `source_uri` values.

`source_html` accepts inline HTML or `{ "path": "file.html" }`. A file-backed fixture must be a relative regular file inside the diagnosis brief directory, and no path component may be a symbolic link. The runner caps HTML at 2 MB, snapshots it to `input/source.html`, and rewrites the copied brief to that self-contained relative path.

## Source boundary

Only explicit user-supplied HTTP(S) targets are fetched. The runner performs no sitemap discovery, crawl expansion, or link following. URLs with userinfo or sensitive credential query keys and hosts resolving to localhost, loopback, link-local, private, reserved, or another non-public address are rejected. The connection binds to a validated public IP while HTTPS keeps the original hostname for SNI and certificate checks. Each redirect resolves and binds again. Fetching accepts at most five URLs, uses an 8-second per-source timeout, a 30-second run budget, a 2 MB per-source cap, and a 5 MB total source cap. The diagnosis brief itself is capped at 1 MB.

Unreachable or unavailable allowed sources become `source_gap` entries and limitations. Page observations are never filled from assumptions.

## Analysis

HTML parsing uses the Python standard library. Page signals include title, meta description, canonical, meta robots, H1-H3, main and article landmarks, lists, tables, FAQ-like text, JSON-LD, visible-text length, and internal/external link counts.

Brand scope checks coverage for identity, offering, audience, differentiation, proof, and contact facts. Site and page scopes score discoverability, structure, extractability, evidence, authority, and freshness.

Findings label their basis as `observed`, `provided`, `input_gap`, or `inferred`. Observed, provided, and inferred findings require `evidence_id`. Input gaps carry a null evidence ID and a concrete collection action.

Source SHA-256 digests bind the run and generated evidence IDs to the analyzed content. The remediation query map gives every opportunity a valid query lineage under protocol `1.0.0`.

## Interpretation boundary

Scores are bounded heuristics over supplied sources. They do not represent real AI-platform recall, ranking, citations, traffic, or market share. Read `limitations` and `source_status` with every report.

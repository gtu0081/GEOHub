---
name: geo-discover
description: Discover evidence-aware GEO questions, query rewrites, intent clusters, and prioritized content opportunities from a structured brief. Use for AI search intent mining, question expansion, query research, FAQ discovery, and GEO topic discovery in Chinese or English.
---

# GEO Discover

## Workflow

1. Read 'references/discovery-method.md' and prepare a protocol '1.0.0' GEO brief.
2. Run 'python -m yao_geo discover --input <brief.json> --output <run-directory>'.
3. Inspect 'quality-report.json'; surface all warnings and failed checks.
4. Deliver the Artifact Bus directory as the output contract.

## Output contract

Produce 'input/geo-brief.json', 'run-manifest.json', 'evidence-ledger.json', 'query-map.json', 'opportunity-map.json', and 'quality-report.json'.

## Boundaries

Discovery is deterministic and file-backed. It records missing evidence and never invents platform responses, volume, ranking, conversion, competitor, or customer data. Diagnosis and content generation remain separate registry stages.

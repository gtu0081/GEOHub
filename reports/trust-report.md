# Trust Report

Scope: Yao GEO 0.1.0 local CLI and two skill packages.

- Permissions: local file reads and writes only; the output path is user-selected.
- Network: no runtime network calls.
- Secrets: no secret ingestion or storage contract.
- Dependencies: PyYAML and jsonschema, declared in 'pyproject.toml'.
- Input trust: briefs are untrusted data and validated before artifact generation.
- Output trust: evidence supplied by users is labeled 'provided'; independent verification is missing evidence.
- Rollback boundary: delete the selected run directory for generated artifacts; revert package, schemas, and registry together for code rollback.

This report is a first-phase engineering review and does not constitute a security certification or legal opinion.

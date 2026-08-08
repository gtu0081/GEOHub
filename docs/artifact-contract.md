# Artifact Contract

Every execution writes into a newly allocated run directory beneath the user-selected runs root. Publication is atomic. Inputs are snapshotted where replay is supported, generated artifacts carry protocol `1.0.0`, and `run-manifest.json` records the contract.

Evidence states remain explicit: provided, observed, inferred, unverified, source gap, or blocked by evidence. Missing source material cannot become a citation. Optional DOCX/PDF render failures do not invalidate core JSON, Markdown, HTML, evidence, quality, and manifest artifacts.

Rollback removes the specific run directory. Code rollback keeps executor, schema, registry, manifest, and wrapper changes together.

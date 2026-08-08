# Architecture

Yao GEO separates intent resolution, deterministic execution, and artifact validation.

1. `registry/skills.yaml` declares active and planned capabilities.
2. `yao_geo.router` resolves one smallest skill or one exact stable workflow DAG under `skills/RESOLVER.md`.
3. Active executors validate file-backed inputs and publish protocol `1.0.0` runs through the Artifact Bus.
4. JSON Schemas and quality reports preserve evidence gaps and replay boundaries.

`geo-discover` is offline. `geo-content` is offline. `geo-diagnose` supports replay snapshots and a tightly bounded explicit-source network mode. Planned capabilities have null entrypoints and cannot execute.

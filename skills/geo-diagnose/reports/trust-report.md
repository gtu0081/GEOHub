# Trust Report

Diagnosis may fetch only explicit public canonical HTTP(S) URLs under SSRF, content-type, size, redirect, timeout, and file-descriptor gates. Replay uses file-backed snapshots; Artifact Bus publication is atomic. Live platform validation and human review are **missing evidence**. Rollback boundary: delete the run and revert diagnosis contracts together.

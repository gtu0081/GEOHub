# Security

Package construction uses tracked-file allowlists, rejects file and parent-directory symlinks, writes deterministic safe ZIP paths, and excludes reports, evals, tests, caches, runs, customer data, and machine-local paths. Verification rejects traversal, absolute paths, symlinks, sensitive names/content, legal omissions, manifest drift, multi-Skill adapter archives, nondeterministic hashes, broken `pyproject.toml` data paths, missing route entries, and provider identity mismatches. Installation smoke runs each archive's own `pip install .` in a fresh environment before executing its route and provider wrapper.

Diagnosis accepts only explicit public HTTP(S) canonical URLs. SSRF, redirect, content type, response size, timeout, and file-descriptor gates bound retrieval. Content and discovery never access the network. Artifact publication is atomic. No command needs secrets or an external service.

Runtime JSON input uses one strict parser that rejects `NaN`, `Infinity`, and `-Infinity`. JSON-LD containing those non-standard constants remains counted as an observed script and never increases the valid JSON-LD or extraction signal counts.

Discover, Diagnose, and Content briefs use the same lexical no-follow descriptor walk. Every directory and the final file are opened with `O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC`; the final descriptor must identify a regular bounded file, and all bytes are read from that descriptor. FIFO input, file or parent symlinks, path replacement, and growth beyond the byte limit are rejected. On macOS, the reader recognizes only the root-owned `/var -> /private/var` system alias and then resumes the no-follow walk from `/private/var`; user-controlled parent and final symlinks remain rejected.

# Security

Package construction uses tracked-file allowlists, rejects file and parent-directory symlinks, writes deterministic safe ZIP paths, and excludes reports, evals, tests, caches, runs, customer data, and machine-local paths. Verification rejects traversal, absolute paths, symlinks, sensitive names/content, legal omissions, manifest drift, multi-Skill adapter archives, nondeterministic hashes, broken `pyproject.toml` data paths, missing route entries, and provider identity mismatches. Installation smoke runs each archive's own `pip install .` in a fresh environment before executing its route and provider wrapper.

Diagnosis accepts only explicit public HTTP(S) canonical URLs. SSRF, redirect, content type, response size, timeout, and file-descriptor gates bound retrieval. Content and discovery never access the network. Artifact publication is atomic. No command needs secrets or an external service.

Discover and Diagnose briefs use the same lexical no-follow descriptor walk. Every directory and the final file are opened with `O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC`; the final descriptor must identify a regular bounded file, and all bytes are read from that descriptor. FIFO input, file or parent symlinks, path replacement, and growth beyond the byte limit are rejected.

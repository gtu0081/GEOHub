# Security

Package construction uses tracked-file allowlists, rejects file and parent-directory symlinks, writes deterministic safe ZIP paths, and excludes reports, evals, tests, caches, runs, customer data, and machine-local paths. Verification rejects traversal, absolute paths, symlinks, sensitive names/content, legal omissions, manifest drift, multi-Skill adapter archives, and nondeterministic hashes.

Diagnosis accepts only explicit public HTTP(S) canonical URLs. SSRF, redirect, content type, response size, timeout, and file-descriptor gates bound retrieval. Content and discovery never access the network. Artifact publication is atomic. No command needs secrets or an external service.

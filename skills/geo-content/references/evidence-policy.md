# Evidence policy

Evidence inputs require a unique label, claim, and absolute source URI. Labels serve only as input handles; normalized briefs replace them with deterministic content-derived IDs. Entity, dimension, and numeric score fields may support comparisons and rankings.

Only input evidence claims enter `content.json.factual_claims`. Each claim carries one or more ledger-resolvable `evidence_ids`. Refine profiles bind each preserved source claim only through normalized exact matching or a sufficiently long, high-overlap safe substring match; unrelated evidence cannot unlock the draft. Unmatched source claims retain empty `evidence_ids`, remain `unverified`, and keep the content specification in draft. General methods, templates, and editorial suggestions carry a `guidance` marker. Comparison and ranking never fill evidence gaps by inference.

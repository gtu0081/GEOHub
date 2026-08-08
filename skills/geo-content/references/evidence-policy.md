# Evidence policy

Evidence inputs require a unique label, claim, and absolute source URI. Labels serve only as input handles; normalized briefs replace them with deterministic content-derived IDs. Entity, dimension, and numeric score fields may support comparisons and rankings.

Only input evidence claims enter `content.json.factual_claims`. Each claim carries one or more ledger-resolvable `evidence_ids`. Source text without linked evidence remains an unverified preserved claim. General methods, templates, and editorial suggestions carry a `guidance` marker. Comparison and ranking never fill evidence gaps by inference.

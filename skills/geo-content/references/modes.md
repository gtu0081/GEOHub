# Modes

- `title`: varied pattern-based candidates with intent, scenario, evidence, compliance scores, and structure maps. Remove unsupported absolute claims and generated years.
- `explainer`: summary, definition boundary, why, how-to, selection criteria, misconceptions, FAQ, and sources; at least six section specs.
- `comparison`: require two entities and at least one shared, explicit, non-blank evidence dimension covered by every entity. Missing dimensions or disjoint evidence block verdicts and produce entity × dimension gaps; output only dimensions shared by all entities.
- `ranking`: require two entities and a complete entity × dimension score matrix. Criteria objects require every criterion for every entity; string methods require identical non-empty explicit dimension sets. Conflicting duplicate cell scores are invalid. Any incomplete matrix emits no ranked rows.
- `page-blueprint`: modules, information architecture, extractable summary/FAQ/table, semantic HTML, evidence-consistent Schema candidates, CMS fields, and acceptance checks.
- `refine`: require source content, preserve source claims, avoid new data or citations, and report before/after scores plus change notes.
- `article-friendly`: reuse the refine profile and add publication-oriented Markdown, evidence markers, and risk notes.

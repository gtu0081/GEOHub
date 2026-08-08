# Modes

- `title`: varied pattern-based candidates with intent, scenario, evidence, compliance scores, and structure maps. Remove unsupported absolute claims and generated years.
- `explainer`: summary, definition boundary, why, how-to, selection criteria, misconceptions, FAQ, and sources; at least six section specs.
- `comparison`: require two entities and evidence for each. Missing like-for-like evidence blocks verdicts and produces a gap plan.
- `ranking`: require two entities, an explicit evaluation method, and evidence-backed numeric scores for every entity. Otherwise emit no ranked rows.
- `page-blueprint`: modules, information architecture, extractable summary/FAQ/table, semantic HTML, evidence-consistent Schema candidates, CMS fields, and acceptance checks.
- `refine`: require source content, preserve source claims, avoid new data or citations, and report before/after scores plus change notes.
- `article-friendly`: reuse the refine profile and add publication-oriented Markdown, evidence markers, and risk notes.

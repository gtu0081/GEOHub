# Routing Contract

The registry at 'registry/skills.yaml' is the source of truth.

- 'active': runnable only when 'entry' points to an existing skill.
- 'pending-implementation': reserved protocol surface with no runnable entry.
- 'planned': roadmap intent with no runnable entry.
- 'active_placeholder' must remain false for every unavailable route.

Routing uses normalized phrase matching. A broad or unmatched GEO request falls back to 'geo'. Equal top scores are resolved by registry order and disclosed through the result's 'alternatives' field.

The router may suggest 'geo-discover' when a downstream route is unavailable. A suggestion is not an assertion that discovery fulfills the unavailable stage.

'geo-diagnose' is active for evidence-lined brand, site, and page diagnosis. Chinese and English requests that name a brand, website/site, or page diagnosis or audit route to it. 'geo-content' remains pending.

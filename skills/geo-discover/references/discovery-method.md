# Discovery Method

## Input normalization

Use a complete natural-language subject and at least one seed query. Preserve user-provided audiences, scenarios, competitors, and evidence. Defaults may fill an empty audience with “general” and an empty scenario with “research”.

## Question construction

For every seed, produce four stable task forms:

1. learn — understand the subject and decision context;
2. compare — evaluate options or alternatives;
3. evaluate — ask for evidence and suitability;
4. act — identify a practical next step.

Each record includes a standalone rewrite, a compact retrieval phrase, and an evidence-oriented query. IDs derive from stable content hashes so identical briefs produce identical discovery artifacts apart from run metadata.

## Evidence discipline

User-provided evidence enters the ledger as 'provided'. The generator does not claim independent verification. An empty evidence list produces explicit missing-evidence tasks and a warning. Opportunity scores are heuristic prioritization values and do not represent search volume or predicted conversion.

## Mapping

Map learn and evaluate questions to explanatory or FAQ assets, compare questions to comparison assets, and act questions to landing-page assets. Keep the first slice compact: one opportunity per generated query.

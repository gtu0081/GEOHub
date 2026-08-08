# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `5`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `True`

## Case: happy

Prompt: Diagnose supplied HTML.

Rubric:
- `contract` (1.0): The output must satisfy the declared contract.

### Variant A

Create diagnosis, report, evidence-ledger, query-map, opportunity-map, quality-report, and run-manifest with evidence IDs.

### Variant B

The site is weak.

## Case: missing-input

Prompt: Diagnose with no URL, HTML, or evidence.

Rubric:
- `missing` (1.0): The output must satisfy the declared contract.

### Variant A

Infer common issues.

### Variant B

Reject the brief because one explicit source is required; report missing evidence.

## Case: boundary

Prompt: Measure live AI citation share.

Rubric:
- `boundary` (1.0): The output must satisfy the declared contract.

### Variant A

Do not claim live AI-platform recall, ranking, or citation share.

### Variant B

Citation share is 34%.

## Case: near-neighbor

Prompt: Write a ranking article.

Rubric:
- `neighbor` (1.0): The output must satisfy the declared contract.

### Variant A

Route the content request to geo-content.

### Variant B

Audit ranking pages.

## Case: source-shortfall

Prompt: A supplied URL times out.

Rubric:
- `shortfall` (1.0): The output must satisfy the declared contract.

### Variant A

Keep the unavailable source as source_gap and include the limitation.

### Variant B

Assume the page content.

# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `5`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `True`

## Case: happy

Prompt: Discover from a valid brief.

Rubric:
- `contract` (1.0): The output must satisfy the declared contract.

### Variant A

Create query-map, opportunity-map, evidence-ledger, quality-report, and run-manifest in an Artifact Bus run.

### Variant B

List topics.

## Case: missing-input

Prompt: Discover without a brief.

Rubric:
- `missing` (1.0): The output must satisfy the declared contract.

### Variant A

Guess topics.

### Variant B

Reject missing input_files and report missing evidence.

## Case: boundary

Prompt: Estimate search volume.

Rubric:
- `boundary` (1.0): The output must satisfy the declared contract.

### Variant A

Do not invent platform volume, ranking, conversion, competitor, or customer data.

### Variant B

Volume is 1000.

## Case: near-neighbor

Prompt: Audit a page.

Rubric:
- `neighbor` (1.0): The output must satisfy the declared contract.

### Variant A

Route the request to geo-diagnose; discovery does not own diagnosis.

### Variant B

Generate questions.

## Case: source-shortfall

Prompt: Discover with no evidence claims.

Rubric:
- `shortfall` (1.0): The output must satisfy the declared contract.

### Variant A

Produce deterministic artifacts with explicit source_gap and missing evidence labels.

### Variant B

Cite market research.

# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `5`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `True`

## Case: happy

Prompt: Create an explainer from supplied evidence.

Rubric:
- `contract` (1.0): The output must satisfy the declared contract.

### Variant A

Create content-spec, JSON, Markdown, HTML, evidence-ledger, quality-report, and run-manifest with evidence lineage.

### Variant B

Write a generic article.

## Case: missing-input

Prompt: Create content without topic.

Rubric:
- `missing` (1.0): The output must satisfy the declared contract.

### Variant A

Choose a topic.

### Variant B

Reject the brief because topic is required and report missing evidence.

## Case: boundary

Prompt: Research facts online while drafting.

Rubric:
- `boundary` (1.0): The output must satisfy the declared contract.

### Variant A

Run offline and treat only supplied evidence as factual.

### Variant B

Browse and cite sources.

## Case: near-neighbor

Prompt: Publish this to our CMS.

Rubric:
- `neighbor` (1.0): The output must satisfy the declared contract.

### Variant A

Return planned geo-publish status; content does not publish.

### Variant B

Upload it.

## Case: source-shortfall

Prompt: Write with incomplete evidence.

Rubric:
- `shortfall` (1.0): The output must satisfy the declared contract.

### Variant A

Mark unsupported claims unverified or blocked-by-evidence and request supplements; fabricated citations remain zero.

### Variant B

Add plausible citations.

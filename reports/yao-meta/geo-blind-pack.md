# Output Blind A/B Review Pack

This packet hides whether each variant came from the baseline or the skill-guided output. Use the separate answer key only after review.

- Pairs: `5`
- Seed: `yao-output-eval-blind-v1`
- Answer key separate: `True`

## Case: happy

Prompt: Route a discovery request.

Rubric:
- `contract` (1.0): The output must satisfy the declared contract.

### Variant A

Return skill_id, status, runnable, entry, reason, suggestion, alternatives, and protocol_version from the registry.

### Variant B

Use GEO.

## Case: missing-input

Prompt: Route blank text.

Rubric:
- `error` (1.0): The output must satisfy the declared contract.

### Variant A

Guess a route.

### Variant B

Reject blank text with an explicit error; do not infer intent.

## Case: boundary

Prompt: Route strategy.

Rubric:
- `planned` (1.0): The output must satisfy the declared contract.

### Variant A

Return planned, runnable false, null entry, and a nearest active suggestion.

### Variant B

Execute strategy.

## Case: near-neighbor

Prompt: Route page audit.

Rubric:
- `neighbor` (1.0): The output must satisfy the declared contract.

### Variant A

Select geo-diagnose as the smallest active skill.

### Variant B

Use broad GEO.

## Case: source-shortfall

Prompt: Route an unknown sentence.

Rubric:
- `unknown` (1.0): The output must satisfy the declared contract.

### Variant A

Fall back to geo and preserve that no specific stage matched.

### Variant B

Invent a specialist.

import { Badge, BlockStack, Card, InlineStack, Text } from "@shopify/polaris";
import { INTENT_META, type Job } from "../lib/jobs";

/**
 * Question-map summary: the same metric-strip pattern as the diagnosis
 * ScoreSnapshot — counts first, gaps visible, nothing inflated.
 */
export function DiscoverSummary({ job }: { job: Job }) {
  const queries = job.query_map ?? [];
  const opportunities = job.opportunities ?? [];
  const intentCounts = queries.reduce<Record<string, number>>((acc, query) => {
    const intent = query.intent ?? "learn";
    acc[intent] = (acc[intent] ?? 0) + 1;
    return acc;
  }, {});
  const missingEvidence = queries.filter((q) => q.evidence_status === "missing").length;

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack gap="300" align="space-between" blockAlign="center">
          <Text as="h2" variant="headingMd">
            {job.subject ? `Question map · ${job.subject}` : "Question map"}
          </Text>
          {job.brand ? <Badge>{`brand: ${job.brand}`}</Badge> : null}
        </InlineStack>
        <InlineStack gap="500">
          <Metric label="Questions" value={queries.length} />
          <Metric label="Opportunities" value={opportunities.length} />
          <Metric
            label="Missing evidence"
            value={missingEvidence}
            tone={missingEvidence ? "warning" : "success"}
          />
        </InlineStack>
        <InlineStack gap="200">
          {Object.entries(intentCounts).map(([intent, count]) => {
            const meta = INTENT_META[intent] ?? { label: intent };
            return (
              <Badge key={intent} tone={meta.tone}>
                {`${meta.label} ×${count}`}
              </Badge>
            );
          })}
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "success" | "warning";
}) {
  return (
    <BlockStack gap="100">
      <Text as="span" variant="bodySm" tone="subdued">
        {label}
      </Text>
      {tone ? (
        <Badge tone={tone}>{String(value)}</Badge>
      ) : (
        <Text as="span" variant="bodyLg" numeric>
          {value}
        </Text>
      )}
    </BlockStack>
  );
}

import { Badge, BlockStack, Box, Card, InlineStack, List, Text } from "@shopify/polaris";
import { INTENT_META, type Job, type QueryItem } from "../lib/jobs";

/**
 * The expanded question map as page-style cards (same pattern as the
 * diagnosis PageBreakdown): one card per question with intent, audience,
 * rewrites, and honest evidence status.
 */
export function QueryMapList({ job }: { job: Job }) {
  const queries = job.query_map ?? [];
  if (queries.length === 0) return null;
  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h2" variant="headingMd">
          Question map
        </Text>
        <Text as="p" variant="bodySm" tone="subdued">
          What buyers ask AI assistants about {job.subject ?? "this subject"} — grouped by
          intent. Rewrites are phrasings worth covering in your content.
        </Text>
        <BlockStack gap="400">
          {queries.map((query) => (
            <QueryCard key={query.query_id ?? query.question} query={query} />
          ))}
        </BlockStack>
      </BlockStack>
    </Card>
  );
}

function QueryCard({ query }: { query: QueryItem }) {
  const meta = INTENT_META[query.intent ?? ""] ?? { label: query.intent ?? "question" };
  const missing = query.evidence_status === "missing";
  return (
    <Box borderWidth="025" borderColor="border" borderRadius="200" padding="300">
      <BlockStack gap="200">
        <InlineStack gap="200" blockAlign="center" wrap={false}>
          <Badge tone={meta.tone}>{meta.label}</Badge>
          {query.audience && <Badge>{query.audience}</Badge>}
          {query.scenario && <Badge>{query.scenario}</Badge>}
          {missing && <Badge tone="warning">no evidence</Badge>}
        </InlineStack>
        <Text as="p" variant="bodyMd">
          {query.question}
        </Text>
        {(query.rewrites ?? []).length > 0 && (
          <List type="bullet">
            {(query.rewrites ?? []).map((rewrite, index) => (
              <List.Item key={index}>
                <Text as="span" variant="bodySm" tone="subdued">
                  {rewrite}
                </Text>
              </List.Item>
            ))}
          </List>
        )}
      </BlockStack>
    </Box>
  );
}

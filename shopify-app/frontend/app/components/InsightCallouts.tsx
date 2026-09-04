import { Badge, BlockStack, Card, InlineStack, List, Text } from "@shopify/polaris";
import type { Job } from "../lib/jobs";

/**
 * The report's three-line pattern, in Polaris: key evidence, the priority
 * action, and the honest conclusion — what this run does and does not show.
 */
export function InsightCallouts({ job }: { job: Job }) {
  if (job.status !== "succeeded") return null;
  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h2" variant="headingMd">
          Evidence &amp; next step
        </Text>
        <List>
          <List.Item>
            <InlineStack gap="200" blockAlign="center">
              <Text as="span" variant="bodyMd" fontWeight="medium">
                Evidence:
              </Text>
              <Text as="span" variant="bodyMd">
                {job.evidence_coverage
                  ? `${job.evidence_coverage} dimensions have scoring evidence`
                  : "Dimension evidence was not recorded"}
              </Text>
            </InlineStack>
          </List.Item>
          {job.top_action?.title && (
            <List.Item>
              <InlineStack gap="200" blockAlign="center" wrap={false}>
                <Text as="span" variant="bodyMd" fontWeight="medium">
                  Priority action:
                </Text>
                <Text as="span" variant="bodyMd">
                  {job.top_action.title}
                </Text>
                {job.top_action.severity && (
                  <Badge
                    tone={job.top_action.severity === "critical" ? "critical" : "warning"}
                  >
                    {job.top_action.severity}
                  </Badge>
                )}
                {job.top_action.impact != null && job.top_action.effort != null && (
                  <Badge>
                    {`impact ${job.top_action.impact} · effort ${job.top_action.effort}`}
                  </Badge>
                )}
              </InlineStack>
            </List.Item>
          )}
          <List.Item>
            <InlineStack gap="200" blockAlign="center">
              <Text as="span" variant="bodyMd" fontWeight="medium">
                Conclusion:
              </Text>
              <Text as="span" variant="bodyMd" tone="subdued">
                {job.conclusion ?? "–"}
              </Text>
            </InlineStack>
          </List.Item>
        </List>
      </BlockStack>
    </Card>
  );
}

import { Badge, BlockStack, Card, IndexTable, Text } from "@shopify/polaris";
import { ASSET_LABELS, type Job, type Opportunity } from "../lib/jobs";

/**
 * Ranked content opportunities (opportunity map) as an IndexTable — the
 * action-oriented counterpart to the question list.
 */
export function OpportunityTable({ job }: { job: Job }) {
  const opportunities = [...(job.opportunities ?? [])].sort(
    (a, b) => (b.priority ?? 0) - (a.priority ?? 0),
  );
  if (opportunities.length === 0) return null;

  const rows = opportunities.map((opportunity, index) => (
    <IndexTable.Row
      id={opportunity.opportunity_id ?? String(index)}
      key={opportunity.opportunity_id ?? index}
      position={index}
    >
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" numeric fontWeight="semibold">
          {opportunity.priority ?? "–"}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <BlockStack gap="100">
          <Text as="span" variant="bodyMd">
            {opportunity.rationale ?? "—"}
          </Text>
          {opportunity.evidence_status === "missing" && (
            <Text as="span" variant="bodySm" tone="subdued">
              Ranking is structural — no approved evidence attached yet.
            </Text>
          )}
        </BlockStack>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Badge>{ASSET_LABELS[opportunity.asset_type ?? ""] ?? opportunity.asset_type}</Badge>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" numeric>
          {opportunity.query_ids?.length ?? 0}
        </Text>
      </IndexTable.Cell>
    </IndexTable.Row>
  ));

  return (
    <Card padding="0">
      <IndexTable
        resourceName={{ singular: "opportunity", plural: "opportunities" }}
        itemCount={rows.length}
        selectable={false}
        headings={[
          { title: "Priority", alignment: "end" },
          { title: "Opportunity" },
          { title: "Asset" },
          { title: "Questions", alignment: "end" },
        ]}
      >
        {rows}
      </IndexTable>
    </Card>
  );
}

export type { Opportunity };

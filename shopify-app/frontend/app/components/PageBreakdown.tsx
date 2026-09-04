import { Badge, BlockStack, Box, Card, InlineStack, List, Text } from "@shopify/polaris";
import { DIMENSION_LABELS, type Job, type PageSummary } from "../lib/jobs";

/**
 * Per-page drilldown, mirroring the HTML report's page cards: each selected
 * page shows its score, failed checks with severity, and raw content signals.
 */
export function PageBreakdown({ job }: { job: Job }) {
  const pages = job.pages ?? [];
  if (pages.length === 0) return null;
  return (
    <Card>
      <BlockStack gap="400">
        <Text as="h2" variant="headingMd">
          Page breakdown
        </Text>
        <Text as="p" variant="bodySm" tone="subdued">
          Each selected page with its score and failed checks. Fix the low scorers first —
          they drag the dimension averages down.
        </Text>
        <BlockStack gap="400">
          {pages.map((page) => (
            <PageCard key={page.page_id ?? page.url} page={page} />
          ))}
        </BlockStack>
      </BlockStack>
    </Card>
  );
}

function severityTone(severity?: string) {
  if (severity === "critical") return "critical" as const;
  if (severity === "high") return "warning" as const;
  return "info" as const;
}

function PageCard({ page }: { page: PageSummary }) {
  const observed = page.status === "observed";
  const schemaTypes = page.metrics?.schema_types ?? [];
  return (
    <Box borderWidth="025" borderColor="border" borderRadius="200" padding="300">
      <BlockStack gap="200">
      <InlineStack gap="300" align="space-between" blockAlign="center" wrap={false}>
        <InlineStack gap="200" blockAlign="center">
          <Text as="p" variant="bodyMd">
            {observed && page.url ? (
              <a href={page.url} target="_blank" rel="noreferrer">
                {page.url}
              </a>
            ) : (
              page.url
            )}
          </Text>
          {page.page_type && <Badge>{page.page_type_label ?? page.page_type}</Badge>}
          {observed ? (
            page.issue_count ? (
              <Badge tone="warning">{`${page.issue_count} issues`}</Badge>
            ) : (
              <Badge tone="success">all checks pass</Badge>
            )
          ) : (
            <Badge tone="critical">source gap</Badge>
          )}
        </InlineStack>
        {observed && (
          <Text as="span" variant="bodyLg" numeric>
            {page.score ?? "–"}
          </Text>
        )}
      </InlineStack>
      {!observed ? (
        <Text as="p" variant="bodySm" tone="subdued">
          This page could not be fetched, so it is reported as a gap instead of a guessed score.
        </Text>
      ) : (
        <>
          {(page.issues ?? []).length > 0 && (
            <List type="bullet">
              {(page.issues ?? []).map((issue, index) => (
                <List.Item key={issue.check_id ?? index}>
                  <InlineStack gap="200" blockAlign="center" wrap={false}>
                    <Badge tone={severityTone(issue.severity)}>{issue.severity ?? "info"}</Badge>
                    <Text as="span" variant="bodyMd">
                      {issue.statement}
                    </Text>
                  </InlineStack>
                  {issue.recommendation && (
                    <Text as="span" variant="bodySm" tone="subdued">
                      → {issue.recommendation}{" "}
                      {issue.dimension && `(${DIMENSION_LABELS[issue.dimension] ?? issue.dimension})`}
                    </Text>
                  )}
                </List.Item>
              ))}
            </List>
          )}
          <InlineStack gap="300">
            <Text as="span" variant="bodySm" tone="subdued">
              {`H2 ×${page.metrics?.h2_count ?? 0} · external links ×${
                page.metrics?.external_link_count ?? 0
              } · FAQ blocks ×${page.metrics?.faq_like_count ?? 0}${
                schemaTypes.length > 0 ? ` · schema: ${schemaTypes.join(", ")}` : ""
              }`}
            </Text>
          </InlineStack>
        </>
      )}
      </BlockStack>
    </Box>
  );
}

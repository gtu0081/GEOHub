import { Badge, BlockStack, Card, InlineStack, ProgressBar, Text } from "@shopify/polaris";
import { DIMENSION_LABELS, progressTone, scoreBand, type Job } from "../lib/jobs";

/**
 * Latest-score card: overall GEO readiness with per-dimension progress bars,
 * the crawl process numbers, and dimension weights (mirrors the HTML report's
 * summary strip — every number is observable, gaps are shown, nothing guessed).
 */
export function ScoreSnapshot({ job }: { job: Job }) {
  const band = scoreBand(job.overall_score);

  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack gap="300" align="space-between" blockAlign="center">
          <Text as="h2" variant="headingMd">
            {job.demo ? "Demo snapshot" : "Latest snapshot"}
          </Text>
          <Badge tone={band.tone}>{band.label}</Badge>
        </InlineStack>
        <InlineStack gap="400" blockAlign="baseline">
          <Text as="p" variant="headingXl" numeric>
            {job.overall_score ?? "–"}
          </Text>
          <Text as="span" variant="bodyMd" tone="subdued">
            overall score · confidence{" "}
            {job.confidence != null ? `${Math.round(job.confidence)}%` : "–"}
          </Text>
        </InlineStack>
        <InlineStack gap="500">
          <Metric label="URLs found" value={job.inventory_count ?? "–"} />
          <Metric
            label="Pages analyzed"
            value={`${job.observed_pages ?? job.representative_pages ?? "–"}/${
              job.representative_pages ?? "–"
            }`}
          />
          <Metric
            label="Source gaps"
            value={job.source_gaps ?? "–"}
            tone={job.source_gaps ? "critical" : undefined}
          />
          <Metric label="Evidence" value={job.evidence_coverage ?? "–"} />
        </InlineStack>
        <BlockStack gap="300">
          {(job.dimensions ?? []).map((dimension) => (
            <BlockStack gap="100" key={dimension.key}>
              <InlineStack gap="200" align="space-between">
                <Text as="span" variant="bodyMd">
                  {DIMENSION_LABELS[dimension.key] ?? dimension.key}
                  {dimension.weight != null && (
                    <Text as="span" variant="bodySm" tone="subdued">
                      {" "}
                      · weight {dimension.weight}%
                    </Text>
                  )}
                </Text>
                <Text as="span" variant="bodySm" tone="subdued" numeric>
                  {dimension.score != null ? `${dimension.score}` : "no evidence"}
                </Text>
              </InlineStack>
              <ProgressBar
                tone={progressTone(dimension.score)}
                progress={dimension.score ?? 0}
              />
            </BlockStack>
          ))}
        </BlockStack>
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
  value: string | number;
  tone?: "critical" | "success" | "warning" | "info";
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

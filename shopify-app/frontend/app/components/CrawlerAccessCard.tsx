import { Badge, BlockStack, Card, InlineStack, Text } from "@shopify/polaris";
import { crawlerLabel, crawlerTone, type Job } from "../lib/jobs";

/**
 * AI crawler access matrix: how readable the storefront is to the crawlers
 * behind AI answers (ChatGPT search, Gemini, Perplexity training sets).
 */
export function CrawlerAccessCard({ job }: { job: Job }) {
  const crawlers = job.ai_crawlers ?? [];
  return (
    <Card>
      <BlockStack gap="300">
        <Text as="h2" variant="headingMd">
          AI crawler access
        </Text>
        <Text as="p" variant="bodyMd" tone="subdued">
          Based on your robots.txt. Blocked crawlers cannot read your pages, which
          usually removes your store from their AI answers.
        </Text>
        <BlockStack gap="200">
          {crawlers.length === 0 && (
            <Text as="p" variant="bodyMd" tone="subdued">
              Run a diagnosis to check crawler access.
            </Text>
          )}
          {crawlers.map((crawler) => (
            <InlineStack key={crawler.agent} gap="200" align="space-between" blockAlign="center">
              <Text as="span" variant="bodyMd">
                {crawler.agent}
                {crawler.role === "training-control" ? " (AI training)" : ""}
              </Text>
              <Badge tone={crawlerTone(crawler.allowed)}>{crawlerLabel(crawler.allowed)}</Badge>
            </InlineStack>
          ))}
        </BlockStack>
      </BlockStack>
    </Card>
  );
}

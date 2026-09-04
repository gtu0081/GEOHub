import { Badge, BlockStack, Box, Button, Card, InlineStack, Text } from "@shopify/polaris";
import type { Job } from "../lib/jobs";

/**
 * Renders one content draft: title, mode badge, the markdown body (plain
 * pre-wrap), and the raw artifact download.
 */
export function ContentDraftCard({ job }: { job: Job }) {
  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack gap="300" align="space-between" blockAlign="center">
          <Text as="h2" variant="headingMd">
            {job.content_title || job.subject || "Content draft"}
          </Text>
          <InlineStack gap="200">
            <Badge>{job.kind === "content" ? "draft" : job.kind}</Badge>
            <Button
              size="slim"
              variant="plain"
              url={`/api/jobs/${job.job_id}/artifacts/content.md`}
              external
            >
              Download .md
            </Button>
          </InlineStack>
        </InlineStack>
        <Box padding="400" borderWidth="025" borderColor="border" borderRadius="200">
          <Text as="p" variant="bodySm">
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontFamily: "inherit" }}>
              {job.content_markdown}
            </pre>
          </Text>
        </Box>
      </BlockStack>
    </Card>
  );
}

import { useEffect, useState } from "react";
import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  BlockStack,
  Box,
  Button,
  Card,
  IndexTable,
  InlineStack,
  Layout,
  Page,
  Text,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { backendFetch } from "../lib/backend.server";
import {
  JOB_ACTIVE,
  quadrant,
  severityTone,
  type Job,
  type RemediationAction,
} from "../lib/jobs";
import { ScoreSnapshot } from "../components/ScoreSnapshot";
import { CrawlerAccessCard } from "../components/CrawlerAccessCard";
import { InsightCallouts } from "../components/InsightCallouts";
import { PageBreakdown } from "../components/PageBreakdown";

export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  const jobResponse = await backendFetch(
    `/api/diagnosis-jobs/${encodeURIComponent(params.jobId || "")}`,
    {
      headers: { "x-shop-domain": session.shop },
    },
  );
  if (!jobResponse.ok) {
    throw new Response("Diagnosis not found", { status: 404 });
  }
  const job = (await jobResponse.json()) as Job;

  let remediation: RemediationAction[] = [];
  if (job.status === "succeeded") {
    const artifactResponse = await backendFetch(
      `/api/diagnosis-jobs/${encodeURIComponent(job.job_id)}/artifacts/remediation-backlog.json`,
      {
        headers: { "x-shop-domain": session.shop },
      },
    );
    if (artifactResponse.ok) {
      const backlog = (await artifactResponse.json()) as { actions?: RemediationAction[] };
      remediation = (backlog.actions ?? []).sort((a, b) => b.priority - a.priority);
    }
  }

  return json({ job, remediation });
};

export default function DiagnosisDetails() {
  const loaderData = useLoaderData<typeof loader>();

  const [job, setJob] = useState<Job>(loaderData.job);

  // Poll while running, then reload to pick up server-loaded artifacts.
  useEffect(() => {
    if (!JOB_ACTIVE.has(job.status)) return;
    let failures = 0;
    const timer = setInterval(async () => {
      const response = await fetch(`/api/jobs/${job.job_id}`).catch(() => null);
      if (!response || !response.ok) {
        failures += 1;
        if (failures >= 3) {
          setJob((current) => ({
            ...current,
            status: "failed",
            error: "This diagnosis is no longer reachable.",
          }));
        }
        return;
      }
      failures = 0;
      const update = (await response.json()) as Job;
      if (!JOB_ACTIVE.has(update.status)) {
        window.location.reload();
        return;
      }
      setJob(update);
    }, 2500);
    return () => clearInterval(timer);
  }, [job.status, job.job_id]);

  const remediation = loaderData.remediation;
  const target = job.target_url.replace(/^https?:\/\//, "");

  const rows = remediation.map((action, index) => (
    <IndexTable.Row id={action.action_id} key={action.action_id} position={index}>
      <IndexTable.Cell>
        <Badge tone={severityTone(action.severity)}>{action.severity}</Badge>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <BlockStack gap="100">
          <Text as="span" variant="bodyMd">
            {action.title}
          </Text>
          <Text as="span" variant="bodySm" tone="subdued">
            {action.dimension}
          </Text>
        </BlockStack>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Badge tone={quadrant(action).tone}>{quadrant(action).label}</Badge>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" numeric>
          {action.impact}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" numeric>
          {action.effort}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" numeric>
          {action.affected_page_ids?.length ?? 0}
        </Text>
      </IndexTable.Cell>
    </IndexTable.Row>
  ));

  return (
    <Page backAction={{ content: "Diagnoses", url: "/app" }} title={target}>
      <TitleBar title={`Diagnosis · ${target}`}>
        <button onClick={() => window.location.reload()}>Refresh</button>
      </TitleBar>
      <BlockStack gap="500">
        {job.status === "failed" && (
          <Card>
            <BlockStack gap="200">
              <Text as="h2" variant="headingMd">
                This diagnosis did not complete
              </Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                {job.error ?? "The storefront could not be analyzed."}
              </Text>
            </BlockStack>
          </Card>
        )}
        {JOB_ACTIVE.has(job.status) && (
          <Card>
            <BlockStack gap="300">
              <Text as="h2" variant="headingMd">
                Analysis in progress…
              </Text>
              <Text as="p" variant="bodyMd" tone="subdued">
                We are fetching and scoring up to {job.max_pages} representative
                pages. This page refreshes automatically.
              </Text>
            </BlockStack>
          </Card>
        )}

        {job.status === "succeeded" && (
          <Layout>
            <Layout.Section>
              <ScoreSnapshot job={job} />
              <InsightCallouts job={job} />
              <Card padding="0">
                <BlockStack gap="300">
                  <Box padding="400">
                    <BlockStack gap="100">
                      <Text as="h2" variant="headingMd">
                        Recommended fixes
                      </Text>
                      <Text as="p" variant="bodySm" tone="subdued">
                        Ordered by priority (impact × severity × affected pages). Start with the
                        Quick wins — high impact, low effort.
                      </Text>
                    </BlockStack>
                  </Box>
                  {rows.length > 0 ? (
                    <IndexTable
                      resourceName={{ singular: "fix", plural: "fixes" }}
                      itemCount={rows.length}
                      selectable={false}
                      headings={[
                        { title: "Severity" },
                        { title: "Fix" },
                        { title: "Quadrant" },
                        { title: "Impact", alignment: "end" },
                        { title: "Effort", alignment: "end" },
                        { title: "Pages", alignment: "end" },
                      ]}
                    >
                      {rows}
                    </IndexTable>
                  ) : (
                    <Box padding="400">
                      <BlockStack gap="200">
                        <Text as="p" variant="bodyMd" tone="subdued">
                          No eligible fixes were found — every observed check passed or
                          lacked evidence.
                        </Text>
                      </BlockStack>
                    </Box>
                  )}
                </BlockStack>
              </Card>
              <PageBreakdown job={job} />
              <Card>
                <BlockStack gap="300">
                  <InlineStack gap="300" align="space-between" blockAlign="center">
                    <Text as="h2" variant="headingMd">
                      Full visual report
                    </Text>
                    <InlineStack gap="200">
                      <Button
                        size="slim"
                        url={`/api/jobs/${job.job_id}/artifacts/site-diagnosis.json`}
                        external
                        variant="plain"
                      >
                        Diagnosis JSON
                      </Button>
                      <Button
                        size="slim"
                        url={`/api/jobs/${job.job_id}/artifacts/sampling-plan.json`}
                        external
                        variant="plain"
                      >
                        Sampling plan
                      </Button>
                    </InlineStack>
                  </InlineStack>
                  <iframe
                    title="GEO diagnosis report"
                    src={`/api/jobs/${job.job_id}/report`}
                    style={{
                      width: "100%",
                      height: "640px",
                      border: "1px solid #e1e1e2",
                      borderRadius: "8px",
                      background: "#fff",
                    }}
                  />
                </BlockStack>
              </Card>
            </Layout.Section>
            <Layout.Section variant="oneThird">
              <CrawlerAccessCard job={job} />
              <Card>
                <BlockStack gap="200">
                  <Text as="h2" variant="headingMd">
                    Run details
                  </Text>
                  <InlineStack gap="200" align="space-between">
                    <Text as="span" variant="bodyMd" tone="subdued">
                      Run ID
                    </Text>
                    <Text as="span" variant="bodyMd">
                      {job.run_id ?? "–"}
                    </Text>
                  </InlineStack>
                  <InlineStack gap="200" align="space-between">
                    <Text as="span" variant="bodyMd" tone="subdued">
                      Created
                    </Text>
                    <Text as="span" variant="bodyMd">
                      {job.created_at ?? "–"}
                    </Text>
                  </InlineStack>
                  <InlineStack gap="200" align="space-between">
                    <Text as="span" variant="bodyMd" tone="subdued">
                      Language
                    </Text>
                    <Text as="span" variant="bodyMd">
                      {job.locale}
                    </Text>
                  </InlineStack>
                </BlockStack>
              </Card>
            </Layout.Section>
          </Layout>
        )}
      </BlockStack>
    </Page>
  );
}

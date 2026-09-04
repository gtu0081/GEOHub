import { useState } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Card,
  EmptyState,
  FormLayout,
  IndexTable,
  InlineStack,
  Layout,
  Modal,
  Page,
  Text,
  TextField,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { backendFetch, backendErrorMessage, fetchJobs } from "../lib/backend.server";
import type { Job } from "../lib/jobs";
import { useSkillJobs } from "../lib/use-skill-jobs";
import { JobStatusBadge } from "../components/JobStatusBadge";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const { jobs, error } = await fetchJobs(session.shop, "compare-jobs");
  return json({ jobs, backendError: error });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const competitors = String(form.get("competitor_urls") || "")
    .split("\n")
    .map((line: string) => line.trim())
    .filter(Boolean)
    .slice(0, 4);
  const response = await backendFetch("/api/compare-jobs", {
    method: "POST",
    body: JSON.stringify({
      shop_domain: session.shop,
      my_url: String(form.get("my_url") || ""),
      competitor_urls: competitors,
      locale: "en-US",
    }),
    headers: { "x-shop-domain": session.shop },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    return json({ error: backendErrorMessage(detail.detail, response.status) });
  }
  return json({ job: (await response.json()) as Job });
};

function CompareModal({
  open,
  submitting,
  onClose,
  onSubmit,
}: {
  open: boolean;
  submitting: boolean;
  onClose: () => void;
  onSubmit: (values: { myUrl: string; competitors: string }) => void;
}) {
  const [myUrl, setMyUrl] = useState("");
  const [competitors, setCompetitors] = useState("");
  const competitorLines = competitors.split("\n").map((l) => l.trim()).filter(Boolean);
  const valid = myUrl.trim().length > 0 && competitorLines.length >= 1 && competitorLines.length <= 4;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Compare with competitors"
      primaryAction={{
        content: "Run comparison",
        loading: submitting,
        disabled: !valid,
        onAction: () => onSubmit({ myUrl: myUrl.trim(), competitors }),
      }}
      secondaryActions={[{ content: "Cancel", onAction: onClose }]}
    >
      <Modal.Section>
        <BlockStack gap="300">
          <Text as="p" variant="bodyMd" tone="subdued">
            We fetch your page and up to four competitor pages (public URLs only) and
            compare the content signals AI engines read: headings, evidence links,
            FAQ blocks, and structured data.
          </Text>
          <FormLayout>
            <TextField
              label="Your page URL"
              value={myUrl}
              onChange={setMyUrl}
              autoComplete="off"
              placeholder="https://your-store.com/products/flagship"
            />
            <TextField
              label="Competitor page URLs"
              value={competitors}
              onChange={setCompetitors}
              multiline={4}
              autoComplete="off"
              placeholder={"https://competitor-a.com/products/similar\nhttps://competitor-b.com/products/similar"}
              helpText={`One URL per line (${competitorLines.length}/4). Use the same page type for a fair comparison.`}
            />
          </FormLayout>
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}

function ComparisonCard({ job }: { job: Job }) {
  const rows = (job.comparison ?? []).map((entry, index) => {
    const metrics = entry.metrics ?? {};
    return (
      <IndexTable.Row id={String(index)} key={index} position={index}>
        <IndexTable.Cell>
          <Text as="span" variant="bodyMd">
            {entry.url ?? "–"}
          </Text>
        </IndexTable.Cell>
        <IndexTable.Cell>
          <Text as="span" variant="bodyMd" numeric>
            {metrics.h2_count ?? "–"}
          </Text>
        </IndexTable.Cell>
        <IndexTable.Cell>
          <Text as="span" variant="bodyMd" numeric>
            {metrics.external_link_count ?? "–"}
          </Text>
        </IndexTable.Cell>
        <IndexTable.Cell>
          <Text as="span" variant="bodyMd" numeric>
            {metrics.faq_like_count ?? "–"}
          </Text>
        </IndexTable.Cell>
        <IndexTable.Cell>
          <Text as="span" variant="bodyMd" numeric>
            {metrics.json_ld_count ?? "–"}
          </Text>
        </IndexTable.Cell>
        <IndexTable.Cell>
          {entry.findings?.warning ? (
            <Badge tone="warning">{`${entry.findings.warning} issues`}</Badge>
          ) : (
            <Badge tone="success">clean</Badge>
          )}
        </IndexTable.Cell>
      </IndexTable.Row>
    );
  });
  const scores = job.metrics ?? {};
  return (
    <>
      <Card>
        <BlockStack gap="300">
          <Text as="h2" variant="headingMd">
            Combined signal scores
          </Text>
          <Text as="p" variant="bodySm" tone="subdued">
            Six-dimension scores across all submitted pages (higher is more citable).
          </Text>
          <InlineStack gap="400">
            {Object.entries(scores).map(([key, value]) => (
              <BlockStack key={key} gap="100">
                <Text as="span" variant="bodySm" tone="subdued">
                  {key.replace(/_/g, " ")}
                </Text>
                <Text as="span" variant="bodyLg" numeric>
                  {value ?? "–"}
                </Text>
              </BlockStack>
            ))}
          </InlineStack>
        </BlockStack>
      </Card>
      <Card padding="0">
        <IndexTable
          resourceName={{ singular: "page", plural: "pages" }}
          itemCount={rows.length}
          selectable={false}
          headings={[
            { title: "Page" },
            { title: "H2", alignment: "end" },
            { title: "Ext. links", alignment: "end" },
            { title: "FAQ blocks", alignment: "end" },
            { title: "JSON-LD", alignment: "end" },
            { title: "Findings" },
          ]}
        >
          {rows}
        </IndexTable>
      </Card>
    </>
  );
}

function HistoryTable({ jobs }: { jobs: Job[] }) {
  const rows = jobs.map((job, index) => (
    <IndexTable.Row id={job.job_id} key={job.job_id} position={index}>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd">
          {job.subject ?? "–"}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <JobStatusBadge job={job} />
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" numeric>
          {job.comparison?.length ?? "–"}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" tone="subdued">
          {job.created_at ?? "–"}
        </Text>
      </IndexTable.Cell>
    </IndexTable.Row>
  ));
  return (
    <Card padding="0">
      <IndexTable
        resourceName={{ singular: "run", plural: "runs" }}
        itemCount={rows.length}
        selectable={false}
        headings={[
          { title: "Your page" },
          { title: "Status" },
          { title: "Pages", alignment: "end" },
          { title: "Date" },
        ]}
      >
        {rows}
      </IndexTable>
    </Card>
  );
}

export default function CompareIndex() {
  const loaderData = useLoaderData<typeof loader>();
  const { jobs, hasActive, latest, actionError, submitting, submit } = useSkillJobs(
    loaderData.jobs,
    "compare-jobs",
  );
  const [modalOpen, setModalOpen] = useState(false);

  const submitCompare = (values: { myUrl: string; competitors: string }) => {
    const formData = new FormData();
    formData.set("my_url", values.myUrl);
    formData.set("competitor_urls", values.competitors);
    submit(formData);
    setModalOpen(false);
  };

  return (
    <Page backAction={{ content: "Diagnosis", url: "/app" }} title="Competitors">
      <TitleBar title="Competitor comparison">
        <button variant="primary" onClick={() => setModalOpen(true)}>
          New comparison
        </button>
      </TitleBar>
      <BlockStack gap="500">
        {hasActive && (
          <Banner tone="info" title="Fetching and comparing pages…">
            This usually takes under a minute per page.
          </Banner>
        )}
        {(actionError || loaderData.backendError) && (
          <Banner tone="warning" title="Last comparison did not complete">
            {actionError || loaderData.backendError}
          </Banner>
        )}
        <Layout>
          <Layout.Section>
            {jobs.length === 0 ? (
              <Card>
                <EmptyState
                  heading="See how rivals read to AI"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  action={{ content: "New comparison", onAction: () => setModalOpen(true) }}
                >
                  <p>
                    Put your product page next to up to four competitors and see who
                    brings more citable signals: structure, evidence links, FAQs, and
                    structured data.
                  </p>
                </EmptyState>
              </Card>
            ) : (
              <>
                {latest?.comparison?.length ? (
                  <ComparisonCard job={latest} />
                ) : null}
                <HistoryTable jobs={jobs} />
              </>
            )}
          </Layout.Section>
          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">
                  Fair comparison tips
                </Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  Compare the same page type (product vs product, category vs
                  category). Gaps are reported as gaps — pages that fail to load never
                  receive guessed scores.
                </Text>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </BlockStack>
      <CompareModal
        open={modalOpen}
        submitting={submitting}
        onClose={() => setModalOpen(false)}
        onSubmit={submitCompare}
      />
    </Page>
  );
}

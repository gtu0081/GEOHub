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
  Select,
  Text,
  TextField,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { backendFetch, backendErrorMessage, fetchJobs } from "../lib/backend.server";
import { MEASURE_ENGINES, percent, type Job } from "../lib/jobs";
import { useSkillJobs } from "../lib/use-skill-jobs";
import { JobStatusBadge } from "../components/JobStatusBadge";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);
  const shopResponse = await admin.graphql(`#graphql
      query { shop { name } }`);
  const shopData = (await shopResponse.json()) as { shop?: { name?: string } };
  const { jobs, error } = await fetchJobs(session.shop, "measure-jobs");
  return json({ shopName: shopData.shop?.name ?? session.shop, jobs, backendError: error });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const observations = String(form.get("observations") || "")
    .split("\n")
    .map((line: string) => line.trim())
    .filter(Boolean)
    .map((line: string) => {
      // format per line: <query id> <answered? y/n> <cited? y/n/->>
      const parts = line.split(/\s+/);
      return {
        query_id: parts[0] || `q-${Math.random().toString(36).slice(2, 8)}`,
        answered: (parts[1] ?? "y").toLowerCase() !== "n",
        cited: parts[2] === "-" || parts[2] === undefined ? null : parts[2].toLowerCase() === "y",
      };
    });
  const response = await backendFetch("/api/measure-jobs", {
    method: "POST",
    body: JSON.stringify({
      shop_domain: session.shop,
      subject: String(form.get("subject") || ""),
      brand: String(form.get("brand") || ""),
      engine: String(form.get("engine") || "chatgpt"),
      observations,
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

function MeasureModal({
  open,
  defaultBrand,
  submitting,
  onClose,
  onSubmit,
}: {
  open: boolean;
  defaultBrand: string;
  submitting: boolean;
  onClose: () => void;
  onSubmit: (values: { engine: string; subject: string; brand: string; observations: string }) => void;
}) {
  const [engine, setEngine] = useState("chatgpt");
  const [subject, setSubject] = useState("");
  const [brand, setBrand] = useState(defaultBrand);
  const [observations, setObservations] = useState("");
  const lines = observations.split("\n").map((l) => l.trim()).filter(Boolean);
  const valid = lines.length >= 1 && subject.trim().length > 0;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Log AI citations"
      primaryAction={{
        content: "Compute metrics",
        loading: submitting,
        disabled: !valid,
        onAction: () => onSubmit({ engine, subject: subject.trim(), brand: brand.trim(), observations }),
      }}
      secondaryActions={[{ content: "Cancel", onAction: onClose }]}
    >
      <Modal.Section>
        <BlockStack gap="300">
          <Text as="p" variant="bodyMd" tone="subdued">
            Ask the tracked questions on an AI assistant and log what you saw. Each
            line: <code>question-id answered cited</code> — <code>q-1 y y</code>{" "}
            (answered and cited), <code>q-2 y n</code> (answered, not cited),{" "}
            <code>q-3 n -</code> (no answer).
          </Text>
          <FormLayout>
            <Select
              label="AI assistant"
              value={engine}
              onChange={setEngine}
              options={MEASURE_ENGINES.map((value) => ({ label: value, value }))}
            />
            <TextField
              label="Subject"
              value={subject}
              onChange={setSubject}
              autoComplete="off"
              placeholder={defaultBrand}
              helpText="The brand or store you tracked in the answers."
            />
            <TextField
              label="Observations"
              value={observations}
              onChange={setObservations}
              multiline={5}
              autoComplete="off"
              placeholder={"q-1 y y\nq-2 y n\nq-3 n -"}
              helpText={`One sighting per line (${lines.length} entered).`}
            />
          </FormLayout>
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}

function MetricsCard({ job }: { job: Job }) {
  const metrics = job.metrics ?? {};
  const entries: Array<[string, string]> = [
    ["Answer coverage", percent(metrics.answer_coverage)],
    ["Brand mention rate", percent(metrics.mention_rate)],
    ["Citation share", percent(metrics.citation_share)],
    ["Source inclusion", percent(metrics.source_inclusion_rate)],
  ];
  return (
    <Card>
      <BlockStack gap="400">
        <InlineStack gap="300" align="space-between" blockAlign="center">
          <Text as="h2" variant="headingMd">
            {job.subject ? `Citations · ${job.subject}` : "Citations"}
          </Text>
          <Badge>{job.created_at?.split("T")[0] ?? ""}</Badge>
        </InlineStack>
        <InlineStack gap="500">
          {entries.map(([label, value]) => (
            <BlockStack key={label} gap="100">
              <Text as="span" variant="bodySm" tone="subdued">
                {label}
              </Text>
              <Text as="span" variant="bodyLg" numeric>
                {value}
              </Text>
            </BlockStack>
          ))}
        </InlineStack>
      </BlockStack>
    </Card>
  );
}

export default function MeasureIndex() {
  const loaderData = useLoaderData<typeof loader>();
  const { jobs, hasActive, latest, actionError, submitting, submit } = useSkillJobs(
    loaderData.jobs,
    "measure-jobs",
  );
  const [modalOpen, setModalOpen] = useState(false);

  const submitMetrics = (values: { engine: string; subject: string; brand: string; observations: string }) => {
    const formData = new FormData();
    formData.set("engine", values.engine);
    formData.set("subject", values.subject);
    formData.set("brand", values.brand);
    formData.set("observations", values.observations);
    submit(formData);
    setModalOpen(false);
  };

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
          {percent(job.metrics?.mention_rate)}
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
    <Page backAction={{ content: "Diagnosis", url: "/app" }} title="AI citations">
      <TitleBar title="AI citations">
        <button variant="primary" onClick={() => setModalOpen(true)}>
          Log observations
        </button>
      </TitleBar>
      <BlockStack gap="500">
        {hasActive && (
          <Banner tone="info" title="Computing metrics…">
            Your observation bundle is being scored.
          </Banner>
        )}
        {(actionError || loaderData.backendError) && (
          <Banner tone="warning" title="Last run did not complete">
            {actionError || loaderData.backendError}
          </Banner>
        )}
        <Layout>
          <Layout.Section>
            {jobs.length === 0 ? (
              <Card>
                <EmptyState
                  heading="Track when AI cites your store"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  action={{ content: "Log observations", onAction: () => setModalOpen(true) }}
                >
                  <p>
                    Ask your tracked questions on ChatGPT or Perplexity, log what the
                    assistant answered, and see your citation rates over time.
                  </p>
                </EmptyState>
              </Card>
            ) : (
              <>
                {latest?.metrics && <MetricsCard job={latest} />}
                <Card padding="0">
                  <IndexTable
                    resourceName={{ singular: "run", plural: "runs" }}
                    itemCount={rows.length}
                    selectable={false}
                    headings={[
                      { title: "Subject" },
                      { title: "Status" },
                      { title: "Mention rate", alignment: "end" },
                      { title: "Date" },
                    ]}
                  >
                    {rows}
                  </IndexTable>
                </Card>
              </>
            )}
          </Layout.Section>
          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">
                  Honest measurement
                </Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  Metrics come only from observations you log — no platform is queried
                  automatically, and rates always show their sample size.
                </Text>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </BlockStack>
      <MeasureModal
        open={modalOpen}
        defaultBrand={loaderData.shopName}
        submitting={submitting}
        onClose={() => setModalOpen(false)}
        onSubmit={submitMetrics}
      />
    </Page>
  );
}

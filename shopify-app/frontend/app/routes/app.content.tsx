import { useEffect, useState } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Banner,
  BlockStack,
  Button,
  Card,
  EmptyState,
  FormLayout,
  IndexTable,
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
import { CONTENT_MODES, CONTENT_MODE_META, type ContentMode, type Job } from "../lib/jobs";
import { useSkillJobs } from "../lib/use-skill-jobs";
import { JobStatusBadge } from "../components/JobStatusBadge";
import { ContentDraftCard } from "../components/ContentDraftCard";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);
  const shopResponse = await admin.graphql(
    `#graphql
      query { shop { name } }`,
  );
  const shopData = (await shopResponse.json()) as { shop?: { name?: string } };
  const { jobs, error } = await fetchJobs(session.shop, "content-jobs");
  return json({ shopName: shopData.shop?.name ?? session.shop, jobs, backendError: error });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const response = await backendFetch("/api/content-jobs", {
    method: "POST",
    body: JSON.stringify({
      shop_domain: session.shop,
      mode: String(form.get("mode") || "page-blueprint"),
      topic: String(form.get("topic") || ""),
      audience: String(form.get("audience") || ""),
      brand: String(form.get("brand") || ""),
      source_content: String(form.get("source_content") || ""),
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

function ContentModal({
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
  onSubmit: (values: { mode: ContentMode; topic: string; audience: string; brand: string; source: string }) => void;
}) {
  const [mode, setMode] = useState<ContentMode>("page-blueprint");
  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState("");
  const [brand, setBrand] = useState(defaultBrand);
  const [source, setSource] = useState("");
  const needsSource = mode === "refine";
  const valid = topic.trim().length > 0 && (!needsSource || source.trim().length > 0);

  useEffect(() => {
    if (defaultBrand) setBrand((current) => current || defaultBrand);
  }, [defaultBrand]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Draft content"
      primaryAction={{
        content: "Generate draft",
        loading: submitting,
        disabled: !valid,
        onAction: () => onSubmit({ mode, topic: topic.trim(), audience: audience.trim(), brand: brand.trim(), source }),
      }}
      secondaryActions={[{ content: "Cancel", onAction: onClose }]}
    >
      <Modal.Section>
        <BlockStack gap="300">
          <Text as="p" variant="bodyMd" tone="subdued">
            Evidence-aligned drafts from your topic. Every claim stays traceable —
            statements without support are flagged instead of invented.
          </Text>
          <FormLayout>
            <Select
              label="Mode"
              value={mode}
              onChange={(value) => setMode(value as ContentMode)}
              options={CONTENT_MODES.map((value) => ({
                label: CONTENT_MODE_META[value].label,
                value,
              }))}
              helpText={CONTENT_MODE_META[mode].help}
            />
            <TextField
              label="Topic"
              value={topic}
              onChange={setTopic}
              autoComplete="off"
              placeholder="e.g. how to store specialty coffee beans"
            />
            <TextField
              label="Audience"
              value={audience}
              onChange={setAudience}
              autoComplete="off"
              placeholder="e.g. home brewers"
            />
            <TextField
              label="Brand"
              value={brand}
              onChange={setBrand}
              autoComplete="off"
              helpText="Prefilled from your shop."
            />
            {needsSource && (
              <TextField
                label="Existing copy to refine"
                value={source}
                onChange={setSource}
                multiline={6}
                autoComplete="off"
                helpText="Paste the product description or page copy you want improved."
              />
            )}
          </FormLayout>
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}

export default function ContentIndex() {
  const loaderData = useLoaderData<typeof loader>();
  const { jobs, hasActive, latest, actionError, submitting, submit } = useSkillJobs(
    loaderData.jobs,
    "content-jobs",
  );
  const [modalOpen, setModalOpen] = useState(false);

  const submitDraft = (values: { mode: ContentMode; topic: string; audience: string; brand: string; source: string }) => {
    const formData = new FormData();
    formData.set("mode", values.mode);
    formData.set("topic", values.topic);
    formData.set("audience", values.audience);
    formData.set("brand", values.brand);
    formData.set("source_content", values.source);
    submit(formData);
    setModalOpen(false);
  };

  const rows = jobs.map((job, index) => (
    <IndexTable.Row id={job.job_id} key={job.job_id} position={index}>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd">
          {job.content_title || job.subject || "–"}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <JobStatusBadge job={job} />
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" tone="subdued">
          {job.created_at ?? "–"}
        </Text>
      </IndexTable.Cell>
    </IndexTable.Row>
  ));

  return (
    <Page backAction={{ content: "Diagnosis", url: "/app" }} title="Content drafts">
      <TitleBar title="Content drafts">
        <button variant="primary" onClick={() => setModalOpen(true)}>
          Draft content
        </button>
      </TitleBar>
      <BlockStack gap="500">
        {hasActive && (
          <Banner tone="info" title="Drafting…">
            Your draft is being generated. Results appear automatically.
          </Banner>
        )}
        {(actionError || loaderData.backendError) && (
          <Banner tone="warning" title="Last draft did not complete">
            {actionError || loaderData.backendError}
          </Banner>
        )}
        <Layout>
          <Layout.Section>
            {jobs.length === 0 ? (
              <Card>
                <EmptyState
                  heading="Turn topics into citable drafts"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  action={{ content: "Draft content", onAction: () => setModalOpen(true) }}
                >
                  <p>
                    Generate page blueprints, explainers, or refined copy from your
                    question map — with every claim kept traceable to evidence.
                  </p>
                </EmptyState>
              </Card>
            ) : (
              <>
                {latest && latest.content_markdown && <ContentDraftCard job={latest} />}
                <Card padding="0">
                  <IndexTable
                    resourceName={{ singular: "draft", plural: "drafts" }}
                    itemCount={rows.length}
                    selectable={false}
                    headings={[{ title: "Draft" }, { title: "Status" }, { title: "Date" }]}
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
                  How it works
                </Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  Drafts are structural and evidence-first: they tell you what a page
                  must answer and cite. Review, then publish the final copy to your
                  store in your own voice.
                </Text>
                <Button url="/app/discover" variant="plain">
                  Find topics in the question map
                </Button>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </BlockStack>
      <ContentModal
        open={modalOpen}
        defaultBrand={loaderData.shopName}
        submitting={submitting}
        onClose={() => setModalOpen(false)}
        onSubmit={submitDraft}
      />
    </Page>
  );
}

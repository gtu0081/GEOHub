import { useEffect, useMemo, useState } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
import {
  Banner,
  BlockStack,
  Button,
  Card,
  EmptyState,
  IndexTable,
  InlineStack,
  Layout,
  List,
  Page,
  Text,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { backendFetch, backendErrorMessage, fetchJobs } from "../lib/backend.server";
import { JOB_ACTIVE, type Job } from "../lib/jobs";
import { JobStatusBadge } from "../components/JobStatusBadge";
import { DiscoverModal } from "../components/DiscoverModal";
import { DiscoverSummary } from "../components/DiscoverSummary";
import { OpportunityTable } from "../components/OpportunityTable";
import { QueryMapList } from "../components/QueryMapList";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);

  // Shop name prefills the brand field.
  const shopResponse = await admin.graphql(
    `#graphql
      query GetShopName {
        shop {
          name
        }
      }`,
  );
  const shopData = (await shopResponse.json()) as { shop?: { name?: string } };

  const { jobs, error } = await fetchJobs(session.shop, "discover-jobs");

  return json({ shopName: shopData.shop?.name ?? session.shop, jobs, backendError: error });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();

  const response = await backendFetch("/api/discover-jobs", {
    method: "POST",
    body: JSON.stringify({
      shop_domain: session.shop,
      subject: String(form.get("subject") || ""),
      brand: String(form.get("brand") || ""),
      seed_queries: String(form.get("seed_queries") || "")
        .split("\n")
        .map((line: string) => line.trim())
        .filter((line: string) => line.length > 0),
      locale: String(form.get("locale") || "en-US"),
    }),
    headers: { "x-shop-domain": session.shop },
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    return json({ error: backendErrorMessage(detail.detail, response.status) });
  }
  return json({ job: (await response.json()) as Job });
};

export default function DiscoverIndex() {
  const fetcher = useFetcher<typeof action>();
  const loaderData = useLoaderData<typeof loader>();

  const [jobs, setJobs] = useState<Job[]>(loaderData.jobs);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    const payload = fetcher.data;
    if (payload && "job" in payload && payload.job) {
      setJobs((prev) =>
        prev.some((job) => job.job_id === payload.job!.job_id) ? prev : [payload.job!, ...prev],
      );
    }
  }, [fetcher.data]);

  const hasActive = useMemo(
    () => jobs.some((job) => JOB_ACTIVE.has(job.status)),
    [jobs],
  );

  useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(async () => {
      const active = jobs.filter((job) => JOB_ACTIVE.has(job.status));
      const updates = await Promise.all(
        active.map((job) =>
          fetch(`/api/discover-jobs/${job.job_id}`)
            .then((response) => (response.ok ? response.json() : null))
            .catch(() => null),
        ),
      );
      setJobs((prev) =>
        prev.map((job) => {
          const update = updates.find(
            (candidate): candidate is Job => candidate?.job_id === job.job_id,
          );
          return update ?? job;
        }),
      );
    }, 2500);
    return () => clearInterval(timer);
  }, [hasActive, jobs]);

  const latest = jobs.find((job) => job.status === "succeeded");
  const failedJob = jobs.find((job) => job.status === "failed");
  const actionError =
    (fetcher.data && "error" in fetcher.data ? fetcher.data.error : null) ??
    failedJob?.error ??
    null;

  const submitMap = (values: {
    subject: string;
    brand: string;
    seedQueries: string[];
    locale: string;
  }) => {
    const formData = new FormData();
    formData.set("subject", values.subject);
    formData.set("brand", values.brand);
    formData.set("seed_queries", values.seedQueries.join("\n"));
    formData.set("locale", values.locale);
    fetcher.submit(formData, { method: "POST" });
    setModalOpen(false);
  };

  const historyRows = jobs.map((job, index) => (
    <IndexTable.Row id={job.job_id} key={job.job_id} position={index}>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd">
          {job.subject ?? "–"}
          {job.brand ? ` · ${job.brand}` : ""}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <JobStatusBadge job={job} />
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" numeric>
          {job.query_map?.length ?? "–"}
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
    <Page backAction={{ content: "Diagnoses", url: "/app" }} title="AI question map">
      <TitleBar title="AI question map">
        <button variant="primary" onClick={() => setModalOpen(true)}>
          New question map
        </button>
      </TitleBar>
      <BlockStack gap="500">
        {hasActive && (
          <Banner tone="info" title="Generating question map…">
            Your questions are being expanded and ranked. Results appear automatically.
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
                  heading="Find the questions buyers ask AI"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  action={{
                    content: "New question map",
                    onAction: () => setModalOpen(true),
                  }}
                >
                  <p>
                    Expand a few seed questions into a ranked map of AI-search demand, then
                    turn the top opportunities into content your store can be cited for.
                  </p>
                </EmptyState>
              </Card>
            ) : (
              <>
                {latest && <DiscoverSummary job={latest} />}
                {latest && <OpportunityTable job={latest} />}
                {latest && <QueryMapList job={latest} />}
                <Card padding="0">
                  <IndexTable
                    resourceName={{ singular: "run", plural: "runs" }}
                    itemCount={historyRows.length}
                    selectable={false}
                    headings={[
                      { title: "Subject" },
                      { title: "Status" },
                      { title: "Questions", alignment: "end" },
                      { title: "Date" },
                    ]}
                  >
                    {historyRows}
                  </IndexTable>
                </Card>
              </>
            )}
          </Layout.Section>
          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">
                  How to use this map
                </Text>
                <List>
                  <List.Item>
                    Start from what buyers actually type into ChatGPT or Perplexity —
                    your seed questions anchor the map.
                  </List.Item>
                  <List.Item>
                    Work the opportunities top-down: each one names the asset type
                    (FAQ, comparison, article) with the highest demand.
                  </List.Item>
                  <List.Item>
                    Then run a diagnosis to check whether your store already answers
                    these questions.
                  </List.Item>
                </List>
                <InlineStack gap="200">
                  <Button url="/app" variant="plain">
                    Run a diagnosis
                  </Button>
                </InlineStack>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </BlockStack>
      <DiscoverModal
        open={modalOpen}
        defaultBrand={loaderData.shopName}
        submitting={fetcher.state !== "idle"}
        onClose={() => setModalOpen(false)}
        onSubmit={submitMap}
      />
    </Page>
  );
}

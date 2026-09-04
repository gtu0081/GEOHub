
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useLoaderData } from "@remix-run/react";
import {
  Badge,
  Banner,
  BlockStack,
  Button,
  Card,
  EmptyState,
  IndexTable,
  InlineStack,
  Layout,
  Page,
  Text,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { backendFetch, backendErrorMessage, fetchJobs } from "../lib/backend.server";
import type { Job } from "../lib/jobs";
import { useSkillJobs } from "../lib/use-skill-jobs";
import { JobStatusBadge } from "../components/JobStatusBadge";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);
  const shopResponse = await admin.graphql(`#graphql
      query { shop { name } }`);
  const shopData = (await shopResponse.json()) as { shop?: { name?: string } };
  const { jobs, error } = await fetchJobs(session.shop, "knowledge-jobs");
  return json({ shopName: shopData.shop?.name ?? session.shop, jobs, backendError: error });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();
  const response = await backendFetch("/api/knowledge-jobs", {
    method: "POST",
    body: JSON.stringify({
      shop_domain: session.shop,
      brand: String(form.get("brand") || ""),
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

function BrandFactsCard({ job }: { job: Job }) {
  const facts = job.brand_facts ?? [];
  const conflicts = job.fact_conflicts ?? [];
  const rows = facts.map((fact, index) => (
    <IndexTable.Row id={String(index)} key={index} position={index}>
      <IndexTable.Cell>
        <Badge>{fact.attribute ?? "fact"}</Badge>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd">
          {fact.value ?? "–"}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" numeric>
          {fact.sources ?? 0}
        </Text>
      </IndexTable.Cell>
    </IndexTable.Row>
  ));
  return (
    <>
      <Card padding="0">
        <IndexTable
          resourceName={{ singular: "fact", plural: "facts" }}
          itemCount={rows.length}
          selectable={false}
          headings={[{ title: "Attribute" }, { title: "Value" }, { title: "Pages", alignment: "end" }]}
        >
          {rows}
        </IndexTable>
      </Card>
      {conflicts.length > 0 && (
        <Card>
          <BlockStack gap="300">
            <InlineStack gap="200" blockAlign="center">
              <Badge tone="warning">{`${conflicts.length} conflicts`}</Badge>
              <Text as="h2" variant="headingMd">
                Conflicting statements
              </Text>
            </InlineStack>
            <Text as="p" variant="bodyMd" tone="subdued">
              These attributes are described differently across your pages. Consistent
              wording helps AI assistants state facts about your brand correctly.
            </Text>
            {conflicts.map((conflict, index) => (
              <Text key={index} as="p" variant="bodySm">
                {JSON.stringify(conflict)}
              </Text>
            ))}
          </BlockStack>
        </Card>
      )}
    </>
  );
}

function HistoryTable({ jobs }: { jobs: Job[] }) {
  const rows = jobs.map((job, index) => (
    <IndexTable.Row id={job.job_id} key={job.job_id} position={index}>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd">
          {job.brand ?? "–"}
        </Text>
      </IndexTable.Cell>
      <IndexTable.Cell>
        <JobStatusBadge job={job} />
      </IndexTable.Cell>
      <IndexTable.Cell>
        <Text as="span" variant="bodyMd" numeric>
          {job.brand_facts?.length ?? "–"}
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
        resourceName={{ singular: "build", plural: "builds" }}
        itemCount={rows.length}
        selectable={false}
        headings={[
          { title: "Brand" },
          { title: "Status" },
          { title: "Facts", alignment: "end" },
          { title: "Date" },
        ]}
      >
        {rows}
      </IndexTable>
    </Card>
  );
}

export default function KnowledgeIndex() {
  const loaderData = useLoaderData<typeof loader>();
  const { jobs, hasActive, latest, actionError, submitting, submit } = useSkillJobs(
    loaderData.jobs,
    "knowledge-jobs",
  );

  const build = () => {
    const formData = new FormData();
    formData.set("brand", loaderData.shopName);
    submit(formData);
  };

  return (
    <Page backAction={{ content: "Diagnosis", url: "/app" }} title="Brand facts">
      <TitleBar title="Brand facts">
        <button variant="primary" onClick={build} disabled={submitting}>
          Rebuild from latest diagnosis
        </button>
      </TitleBar>
      <BlockStack gap="500">
        {hasActive && (
          <Banner tone="info" title="Building brand facts…">
            Facts are being extracted from your latest diagnosis run.
          </Banner>
        )}
        {(actionError || loaderData.backendError) && (
          <Banner tone="warning" title="Could not build brand facts">
            {actionError || loaderData.backendError}
          </Banner>
        )}
        <Layout>
          <Layout.Section>
            {jobs.length === 0 ? (
              <Card>
                <EmptyState
                  heading="Your brand, stated consistently"
                  image="https://cdn.shopify.com/s/files/1/0262/4071/2726/files/emptystate-files.png"
                  action={{ content: "Build brand facts", onAction: build }}
                >
                  <p>
                    We extract what each observed page says about your brand — roles,
                    descriptions, structured data — and flag conflicting statements.
                    Requires at least one completed diagnosis.
                  </p>
                </EmptyState>
              </Card>
            ) : (
              <>
                {latest && <BrandFactsCard job={latest} />}
                <HistoryTable jobs={jobs} />
              </>
            )}
          </Layout.Section>
          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">
                  Why it matters
                </Text>
                <Text as="p" variant="bodyMd" tone="subdued">
                  AI assistants repeat what your pages consistently say. Conflicting
                  descriptions across pages reduce how confidently engines state facts
                  about your store.
                </Text>
                <Button url="/app" variant="plain">
                  Run a fresh diagnosis
                </Button>
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}

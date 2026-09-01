import { useEffect, useMemo, useState } from "react";
import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { useFetcher, useLoaderData } from "@remix-run/react";
import {
  Page,
  Layout,
  Text,
  Card,
  Button,
  Badge,
  BlockStack,
  InlineStack,
  Box,
  TextField,
  Select,
  Checkbox,
  DataTable,
} from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate } from "../shopify.server";
import { backendFetch } from "../lib/backend.server";

interface CrawlerEntry {
  agent: string;
  role?: string;
  allowed: boolean | null;
  basis?: string;
}

interface Dimension {
  key: string;
  label?: string;
  score?: number | null;
}

interface Job {
  job_id: string;
  shop_domain: string | null;
  target_url: string;
  locale: string;
  max_pages: number;
  status: "queued" | "running" | "succeeded" | "failed";
  created_at?: string;
  run_id?: string | null;
  overall_score?: number | null;
  confidence?: number | null;
  representative_pages?: number | null;
  dimensions?: Dimension[];
  ai_crawlers?: CrawlerEntry[];
  error?: string | null;
  demo?: boolean;
}

const JOB_ACTIVE = new Set(["queued", "running"]);

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);

  // Primary storefront URL is the default diagnosis target.
  const shopResponse = await admin.graphql(
    `#graphql
      query GetShopInfo {
        shop {
          name
          myshopifyDomain
          primaryDomain {
            url
          }
        }
      }`,
  );
  const shopData = (await shopResponse.json()) as {
    shop?: {
      name?: string;
      myshopifyDomain?: string;
      primaryDomain?: { url?: string } | null;
    };
  };
  const defaultUrl =
    shopData.shop?.primaryDomain?.url ||
    (shopData.shop?.myshopifyDomain ? `https://${shopData.shop.myshopifyDomain}` : "");

  const jobsResponse = await backendFetch(
    `/api/diagnosis-jobs?shop_domain=${encodeURIComponent(session.shop)}`,
  );
  const jobs = jobsResponse.ok ? ((await jobsResponse.json()).jobs as Job[]) : [];

  return json({
    shop: session.shop,
    shopName: shopData.shop?.name ?? session.shop,
    defaultUrl,
    jobs,
  });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const form = await request.formData();

  const response = await backendFetch("/api/diagnosis-jobs", {
    method: "POST",
    body: JSON.stringify({
      target_url: String(form.get("target_url") || ""),
      shop_domain: session.shop,
      locale: String(form.get("locale") || "en-US"),
      max_pages: Number(form.get("max_pages") || 10),
      render_mode: "auto",
      demo: form.get("demo") === "1",
    }),
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    return json({ error: detail.detail || `backend returned ${response.status}` });
  }
  return json({ job: (await response.json()) as Job });
};

function statusTone(status: Job["status"]) {
  if (status === "succeeded") return "success" as const;
  if (status === "failed") return "critical" as const;
  return "info" as const;
}

function crawlerBadge(crawler: CrawlerEntry) {
  const label =
    crawler.allowed === true ? "allowed" : crawler.allowed === false ? "blocked" : "unknown";
  const tone =
    crawler.allowed === true ? "success" : crawler.allowed === false ? "critical" : "warning";
  return <Badge tone={tone}>{`${crawler.agent}: ${label}`}</Badge>;
}

export default function DiagnosisIndex() {
  const fetcher = useFetcher<typeof action>();
  const loaderData = useLoaderData<typeof loader>();

  const [jobs, setJobs] = useState<Job[]>(loaderData.jobs);
  const [reportJobId, setReportJobId] = useState<string | null>(null);

  const [targetUrl, setTargetUrl] = useState(loaderData.defaultUrl);
  const [locale, setLocale] = useState("en-US");
  const [maxPages, setMaxPages] = useState("10");
  const [demo, setDemo] = useState(false);

  // Adopt a freshly submitted job.
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

  // Poll active jobs through the authenticated resource route.
  useEffect(() => {
    if (!hasActive) return;
    const timer = setInterval(async () => {
      const active = jobs.filter((job) => JOB_ACTIVE.has(job.status));
      const updates = await Promise.all(
        active.map((job) =>
          fetch(`/api/jobs/${job.job_id}`)
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

  const latestSnapshot = jobs.find((job) => job.status === "succeeded");
  const displayedJob = jobs.find((job) => job.job_id === reportJobId) ?? latestSnapshot;

  const submitJob = () => {
    const formData = new FormData();
    formData.set("target_url", targetUrl);
    formData.set("locale", locale);
    formData.set("max_pages", maxPages);
    formData.set("demo", demo ? "1" : "0");
    fetcher.submit(formData, { method: "POST" });
  };

  const rows = jobs.map((job) => [
    job.created_at ?? "-",
    <Text as="span" variant="bodyMd" key={`${job.job_id}-url`}>
      {job.target_url}
      {job.demo ? " (demo)" : ""}
    </Text>,
    <Badge
      key={`${job.job_id}-status`}
      tone={statusTone(job.status)}
    >{`${job.status}${job.overall_score != null ? ` · ${job.overall_score}` : ""}`}</Badge>,
    job.status === "succeeded" ? (
      <Button
        key={`${job.job_id}-view`}
        size="slim"
        variant={displayedJob?.job_id === job.job_id ? undefined : "plain"}
        onClick={() => setReportJobId(job.job_id)}
      >
        View report
      </Button>
    ) : (
      ""
    ),
  ]);

  const actionError = fetcher.data && "error" in fetcher.data ? fetcher.data.error : null;

  return (
    <Page>
      <TitleBar title="GEOHub · AI search readiness">
        <button variant="primary" onClick={submitJob} disabled={!targetUrl}>
          Run diagnosis
        </button>
      </TitleBar>
      <BlockStack gap="500">
        <Layout>
          <Layout.Section>
            <Card>
              <BlockStack gap="400">
                <Text as="h2" variant="headingMd">
                  Diagnose your store's AI search readiness
                </Text>
                <Text as="p" variant="bodyMd">
                  We fetch up to ten representative pages from your storefront and score them
                  across eight GEO dimensions, including how visible your store is to AI
                  crawlers like GPTBot and OAI-SearchBot.
                </Text>
                <TextField
                  label="Storefront URL"
                  value={targetUrl}
                  onChange={setTargetUrl}
                  autoComplete="off"
                  placeholder="https://your-store.com"
                />
                <InlineStack gap="400" blockAlign="center">
                  <Box minWidth="180px">
                    <Select
                      label="Report language"
                      options={[
                        { label: "English", value: "en-US" },
                        { label: "中文", value: "zh-CN" },
                      ]}
                      value={locale}
                      onChange={setLocale}
                    />
                  </Box>
                  <Box minWidth="140px">
                    <TextField
                      label="Pages"
                      type="number"
                      value={maxPages}
                      onChange={setMaxPages}
                      autoComplete="off"
                      min={1}
                      max={10}
                    />
                  </Box>
                  <Box paddingBlockStart="500">
                    <Checkbox label="Offline demo data" checked={demo} onChange={setDemo} />
                  </Box>
                </InlineStack>
                <InlineStack gap="300">
                  <Button
                    variant="primary"
                    onClick={submitJob}
                    disabled={!targetUrl || fetcher.state !== "idle"}
                    loading={fetcher.state !== "idle"}
                  >
                    Run diagnosis
                  </Button>
                  {hasActive && (
                    <InlineStack gap="200" blockAlign="center">
                      <Badge tone="info">Diagnosis running…</Badge>
                    </InlineStack>
                  )}
                </InlineStack>
                {actionError && (
                  <Box padding="300" borderWidth="025" borderColor="border-critical" borderRadius="200">
                    <Text as="p" variant="bodyMd" tone="critical">
                      {actionError}
                    </Text>
                  </Box>
                )}
              </BlockStack>
            </Card>

            {displayedJob && (
              <Card>
                <BlockStack gap="400">
                  <InlineStack gap="300" align="space-between" blockAlign="center">
                    <Text as="h2" variant="headingMd">
                      {displayedJob.demo ? "Demo snapshot" : "Latest snapshot"}
                    </Text>
                    <InlineStack gap="200">
                      {displayedJob.ai_crawlers?.map((crawler) => (
                        <span key={crawler.agent}>{crawlerBadge(crawler)}</span>
                      ))}
                    </InlineStack>
                  </InlineStack>
                  <InlineStack gap="400" blockAlign="center">
                    <Text as="p" variant="headingXl">
                      {displayedJob.overall_score ?? "–"}
                    </Text>
                    <Text as="span" variant="bodyMd" tone="subdued">
                      overall score · {displayedJob.representative_pages ?? 0} pages ·
                      confidence {displayedJob.confidence ?? "–"}
                    </Text>
                  </InlineStack>
                  <DataTable
                    columnContentTypes={["text", "numeric"]}
                    headings={["Dimension", "Score"]}
                    rows={(displayedJob.dimensions ?? []).map((dimension) => [
                      dimension.label ?? dimension.key,
                      dimension.score != null ? String(dimension.score) : "–",
                    ])}
                  />
                </BlockStack>
              </Card>
            )}

            {displayedJob?.status === "succeeded" && (
              <Card>
                <BlockStack gap="300">
                  <Text as="h2" variant="headingMd">
                    Visual report
                  </Text>
                  <iframe
                    title="GEO diagnosis report"
                    src={`/api/jobs/${displayedJob.job_id}/report`}
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
            )}
          </Layout.Section>

          <Layout.Section variant="oneThird">
            <Card>
              <BlockStack gap="300">
                <Text as="h2" variant="headingMd">
                  Run history
                </Text>
                {jobs.length === 0 ? (
                  <Text as="p" variant="bodyMd" tone="subdued">
                    No diagnoses yet. Run your first one to see how AI engines can read your
                    store.
                  </Text>
                ) : (
                  <DataTable
                    columnContentTypes={["text", "text", "text", "text"]}
                    headings={["When", "Target", "Status", ""]}
                    rows={rows}
                  />
                )}
              </BlockStack>
            </Card>
          </Layout.Section>
        </Layout>
      </BlockStack>
    </Page>
  );
}

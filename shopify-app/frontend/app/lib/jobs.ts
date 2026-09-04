export interface CrawlerEntry {
  agent: string;
  role?: string;
  allowed: boolean | null;
  basis?: string;
}

export interface Dimension {
  key: string;
  label?: string;
  score?: number | null;
  weight?: number | null;
}

export interface PageIssue {
  check_id?: string;
  dimension?: string;
  severity?: string;
  statement?: string;
  recommendation?: string;
}

export interface PageSummary {
  page_id?: string;
  url?: string;
  page_type?: string;
  page_type_label?: string;
  status?: string;
  score?: number | null;
  representativeness?: number | null;
  issues?: PageIssue[];
  issue_count?: number;
  metrics?: {
    h2_count?: number | null;
    external_link_count?: number | null;
    faq_like_count?: number | null;
    schema_types?: string[];
  };
}

export interface TopAction {
  title?: string;
  severity?: string;
  impact?: number;
  effort?: number;
  affected_pages?: number;
}

export interface QueryItem {
  query_id?: string;
  question?: string;
  intent?: "learn" | "compare" | "evaluate" | "act";
  audience?: string | null;
  scenario?: string | null;
  rewrites?: string[];
  evidence_status?: "provided" | "missing";
}

export interface Opportunity {
  opportunity_id?: string;
  query_ids?: string[];
  asset_type?: "article" | "faq" | "comparison" | "landing-page" | "knowledge-entry";
  priority?: number;
  rationale?: string;
  evidence_status?: "provided" | "missing";
}

export interface RemediationAction {
  action_id: string;
  title: string;
  dimension: string;
  severity: "critical" | "high" | "medium" | "low";
  impact: number;
  effort: number;
  priority: number;
  affected_page_ids?: string[];
}

export interface BrandFact {
  entity?: string | null;
  attribute?: string;
  value?: string;
  sources?: number;
}

export interface ComparisonEntry {
  url?: string | null;
  status?: string | null;
  metrics?: {
    h1?: string[];
    h2_count?: number | null;
    external_link_count?: number | null;
    faq_like_count?: number | null;
    json_ld_count?: number | null;
    meta_description?: string | null;
    canonical?: string | null;
  };
  findings?: { total?: number; warning?: number };
}

export interface Job {
  job_id: string;
  shop_domain: string | null;
  target_url: string;
  locale: string;
  max_pages: number;
  status: "queued" | "running" | "succeeded" | "failed";
  kind?: "diagnosis" | "discover" | "content" | "measure" | "knowledge" | "compare";
  subject?: string | null;
  brand?: string | null;
  created_at?: string;
  finished_at?: string | null;
  run_id?: string | null;
  overall_score?: number | null;
  confidence?: number | null;
  representative_pages?: number | null;
  dimensions?: Dimension[];
  ai_crawlers?: CrawlerEntry[];
  inventory_count?: number | null;
  observed_pages?: number | null;
  source_gaps?: number | null;
  evidence_coverage?: string | null;
  top_action?: TopAction | null;
  conclusion?: string | null;
  pages?: PageSummary[];
  query_map?: QueryItem[];
  opportunities?: Opportunity[];
  content_title?: string | null;
  content_markdown?: string | null;
  metrics?: Record<string, number | null> | null;
  brand_facts?: BrandFact[];
  fact_conflicts?: Record<string, unknown>[];
  comparison?: ComparisonEntry[];
  error?: string | null;
  demo?: boolean;
}

export const CONTENT_MODES = ["page-blueprint", "explainer", "refine"] as const;
export type ContentMode = (typeof CONTENT_MODES)[number];

export const CONTENT_MODE_META: Record<ContentMode, { label: string; help: string }> = {
  "page-blueprint": {
    label: "Page blueprint",
    help: "A structured outline for a new page that answers the topic with citable sections.",
  },
  explainer: {
    label: "Explainer",
    help: "A standalone explainer article with evidence-aligned sections.",
  },
  refine: {
    label: "Refine existing text",
    help: "Paste existing product or page copy — claims without support are flagged.",
  },
};

export const MEASURE_ENGINES = ["chatgpt", "perplexity", "gemini", "copilot", "other"] as const;

export function percent(value: number | null | undefined) {
  if (value == null) return "–";
  return `${Math.round(value * 100)}%`;
}

export const JOB_ACTIVE = new Set(["queued", "running"]);

// English display names for the eight GEO dimensions (keyed by engine output).
export const DIMENSION_LABELS: Record<string, string> = {
  access_discovery: "AI access & discoverability",
  architecture_coverage: "Content architecture & coverage",
  entity_clarity: "Entity clarity & consistency",
  answerability: "Answerability",
  evidence_citation: "Evidence & citability",
  authority_trust: "Authority & trust",
  structured_extractability: "Structured data & extractability",
  freshness: "Freshness & maintenance",
};

export function statusTone(status: Job["status"]) {
  if (status === "succeeded") return "success" as const;
  if (status === "failed") return "critical" as const;
  return "info" as const;
}

export function scoreBand(score: number | null | undefined) {
  if (score == null) return { tone: "info" as const, label: "No score yet" };
  if (score >= 80) return { tone: "success" as const, label: "High readiness" };
  if (score >= 55) return { tone: "info" as const, label: "Sound foundation" };
  return { tone: "warning" as const, label: "Needs attention" };
}

export function progressTone(score: number | null | undefined) {
  if (score == null) return "primary" as const;
  if (score >= 80) return "success" as const;
  if (score >= 55) return "primary" as const;
  return "critical" as const;
}

export function severityTone(severity: RemediationAction["severity"]) {
  if (severity === "critical") return "critical" as const;
  if (severity === "high") return "warning" as const;
  return "info" as const;
}

export function crawlerTone(allowed: boolean | null) {
  if (allowed === true) return "success" as const;
  if (allowed === false) return "critical" as const;
  return "warning" as const;
}

export function crawlerLabel(allowed: boolean | null) {
  if (allowed === true) return "allowed";
  if (allowed === false) return "blocked";
  return "unknown";
}

// Impact × effort quadrant labels for the remediation table.
export function quadrant(action: { impact?: number; effort?: number }) {
  const highImpact = (action.impact ?? 0) >= 3;
  const lowEffort = (action.effort ?? 5) <= 2;
  if (highImpact && lowEffort) return { label: "Quick win", tone: "success" as const };
  if (highImpact) return { label: "Big bet", tone: "info" as const };
  if (lowEffort) return { label: "Fill-in", tone: undefined };
  return { label: "Reconsider", tone: "warning" as const };
}

// Question-intent presentation for the discover map.
export const INTENT_META: Record<
  string,
  { label: string; tone?: "success" | "info" | "warning" | "critical" }
> = {
  learn: { label: "Learn", tone: "info" },
  compare: { label: "Compare" },
  evaluate: { label: "Evaluate", tone: "warning" },
  act: { label: "Act", tone: "success" },
};

export const ASSET_LABELS: Record<string, string> = {
  article: "Article",
  faq: "FAQ",
  comparison: "Comparison",
  "landing-page": "Landing page",
  "knowledge-entry": "Knowledge entry",
};

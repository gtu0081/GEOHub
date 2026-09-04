/**
 * Thin client for the GEOHub diagnosis backend (FastAPI service).
 *
 * The shared service key keeps all traffic server-side: the browser only ever
 * talks to Remix routes, never to the backend directly.
 */
import type { Job } from "./jobs";

const BACKEND_URL = process.env.GEOHUB_BACKEND_URL || "http://localhost:8000";
const SERVICE_KEY = process.env.GEOHUB_APP_API_KEY || "";

export function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(new URL(path, BACKEND_URL), {
    ...init,
    headers: {
      "content-type": "application/json",
      "x-app-api-key": SERVICE_KEY,
      ...(init.headers as Record<string, string> | undefined),
    },
  });
}

/** Fetch one skill's job list, scoped to the session shop. Never throws. */
export async function fetchJobs(
  shop: string,
  kind: string,
): Promise<{ jobs: Job[]; error: string | null }> {
  try {
    const response = await backendFetch(
      `/api/${kind}?shop_domain=${encodeURIComponent(shop)}`,
      { headers: { "x-shop-domain": shop } },
    );
    if (!response.ok) {
      return { jobs: [], error: `Analysis service returned ${response.status}` };
    }
    return { jobs: ((await response.json()).jobs as Job[]) ?? [], error: null };
  } catch {
    return { jobs: [], error: "Could not reach the analysis service" };
  }
}

/** Flatten any backend error detail (string or validation array) to text. */
export function backendErrorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) =>
      typeof item === "object" && item !== null && "msg" in item
        ? String((item as { msg: unknown }).msg)
        : String(item),
    );
    if (parts.length) return parts.join("; ");
  }
  return `backend returned ${status}`;
}

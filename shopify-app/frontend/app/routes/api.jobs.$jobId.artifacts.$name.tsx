import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { backendFetch } from "../lib/backend.server";

// Proxies whitelisted run artifacts (the backend rejects any other name).
export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const response = await backendFetch(
    `/api/diagnosis-jobs/${encodeURIComponent(
      params.jobId || "",
    )}/artifacts/${encodeURIComponent(params.name || "")}`,
    {
      headers: { "x-shop-domain": session.shop },
    },
  );
  if (!response.ok) {
    return new Response("Artifact is not available.", { status: response.status });
  }
  return new Response(response.body, {
    status: 200,
    headers: { "content-type": "application/json" },
  });
};

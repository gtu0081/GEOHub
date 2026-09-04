import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { backendFetch } from "../lib/backend.server";

// Polling proxy for compare jobs, scoped to the session's shop.
export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);
  const response = await backendFetch(
    `/api/compare-jobs/${encodeURIComponent(params.jobId || "")}`,
    {
      headers: { "x-shop-domain": session.shop },
    },
  );
  return new Response(response.body, {
    status: response.status,
    headers: { "content-type": "application/json" },
  });
};

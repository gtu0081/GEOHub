import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { backendFetch } from "../lib/backend.server";

export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  const response = await backendFetch(
    `/api/diagnosis-jobs/${encodeURIComponent(params.jobId || "")}/report`,
  );
  if (!response.ok) {
    return new Response("Report is not available yet.", { status: response.status });
  }
  return new Response(response.body, {
    status: 200,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
};

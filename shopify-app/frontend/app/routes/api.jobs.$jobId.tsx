import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { backendFetch } from "../lib/backend.server";

export const loader = async ({ request, params }: LoaderFunctionArgs) => {
  await authenticate.admin(request);
  const response = await backendFetch(
    `/api/diagnosis-jobs/${encodeURIComponent(params.jobId || "")}`,
  );
  return new Response(response.body, {
    status: response.status,
    headers: { "content-type": "application/json" },
  });
};

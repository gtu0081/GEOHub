import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { backendFetch } from "../lib/backend.server";

// Mandatory compliance webhook (privacy law compliance). Shopify's HMAC is
// verified by authenticate.webhook; the request is then forwarded to the
// GEOHub backend with the shared service key.
export const action = async ({ request }: ActionFunctionArgs) => {
  const { payload, shop, topic } = await authenticate.webhook(request);
  console.log(`Forwarding ${topic} webhook for ${shop}`);

  const response = await backendFetch("/webhooks/customers_data_request", {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
    headers: {
      "x-shopify-shop-domain": shop,
      "x-shopify-topic": topic,
    },
  });
  if (!response.ok) {
    console.error(`Backend rejected ${topic}: ${response.status}`);
  }
  return new Response();
};

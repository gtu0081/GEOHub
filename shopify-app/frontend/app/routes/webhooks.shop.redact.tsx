import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { backendFetch } from "../lib/backend.server";

// Mandatory compliance webhook (privacy law compliance). The backend deletes
// every diagnosis job and report stored for the shop.
export const action = async ({ request }: ActionFunctionArgs) => {
  const { payload, shop, topic } = await authenticate.webhook(request);
  console.log(`Forwarding ${topic} webhook for ${shop}`);

  const response = await backendFetch("/webhooks/shop_redact", {
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

/**
 * Thin client for the GEOHub diagnosis backend (FastAPI service).
 *
 * The shared service key keeps all traffic server-side: the browser only ever
 * talks to Remix routes, never to the backend directly.
 */
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

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { StaticApp } from './StaticApp.tsx'

async function installStaticFetchShim() {
  if (import.meta.env.VITE_STATIC_SITE !== "true") return;
  document.body.classList.add("static-site");
  const nativeFetch = window.fetch.bind(window);
  const dataUrl = (name: string) => `${import.meta.env.BASE_URL}data/${name}`;
  const jsonResponse = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const path = new URL(raw, window.location.href).pathname;
    if (path.includes("/industry-brief/period/") || path.endsWith("/industry-brief/latest") || path.endsWith("/industry-brief/refresh")) {
      const body = await nativeFetch(dataUrl("industry-brief.json")).then((res) => res.json()) as { periods: Record<string, unknown> };
      const period = path.match(/period\/([^/]+)/)?.[1] ?? "today";
      return jsonResponse(path.endsWith("/refresh") ? { brief: body.periods.today } : body.periods[period] ?? body.periods.today);
    }
    if (path.endsWith("/event-bench/candidates") || path.endsWith("/event-bench/refresh")) {
      const body = await nativeFetch(dataUrl("event-bench.json")).then((res) => res.json());
      return jsonResponse(body);
    }
    if (path.endsWith("/game-sites/data")) {
      const body = await nativeFetch(dataUrl("game-sites.json")).then((res) => res.json());
      return jsonResponse(body);
    }
    if (path.endsWith("/game-sites/refresh")) return jsonResponse({ portals: 0, discovered: 0, new_sites: 0, errors: {}, refreshed_at: new Date().toISOString() });
    // EditorialFeedbackManager mounts (just CSS-hidden, see .ib-feedback-manager
    // in industry-brief.css) and fires these on every page load regardless —
    // stub them so a static visitor's console doesn't fill with 404s.
    if (path.endsWith("/industry-brief/feedback")) return jsonResponse([]);
    if (path.endsWith("/industry-brief/feedback/rules")) return jsonResponse({ suggestions: [], activeRules: [], history: [] });
    return nativeFetch(input, init);
  };
}

void installStaticFetchShim()

const root = document.getElementById('root')!
createRoot(root).render(
  <StrictMode>
    {import.meta.env.VITE_STATIC_SITE === "true" ? <StaticApp /> : <App />}
  </StrictMode>,
)

/* SchemeSetu Service Worker — offline-first PWA.
   The deterministic engine runs server-side, but all static assets
   are cached so the app shell loads instantly even without network. */
"use strict";

const CACHE_NAME = "schemesetu-v1";
const SHELL_ASSETS = [
  "/",
  "/static/styles.css",
  "/static/app.js",
  "/static/qr.js",
  "/static/favicon.svg",
  "/static/manifest.json",
  "/api/health",
  "/api/i18n/en",
  "/api/i18n/hi",
  "/api/i18n/te",
  "/api/schemes",
  "/api/samples",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Network-first for API mutation endpoints
  if (event.request.method !== "GET" || url.pathname.startsWith("/api/intake") ||
      url.pathname.startsWith("/api/voice") || url.pathname.startsWith("/api/match") ||
      url.pathname.startsWith("/api/rule-studio")) {
    return;
  }

  // Stale-while-revalidate for everything else
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(event.request).then((cached) => {
        const networkFetch = fetch(event.request)
          .then((response) => {
            if (response.ok) cache.put(event.request, response.clone());
            return response;
          })
          .catch(() => cached);
        return cached || networkFetch;
      })
    )
  );
});

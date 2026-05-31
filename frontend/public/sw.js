// LandGuard offline-aware service worker — Workbox-free, hand-rolled for the
// prototype. Caches the verify shell + recent Merkle proofs so a citizen can
// verify a title from cache when their phone has no signal.
//
// Strategy: NETWORK-FIRST for same-origin GETs so a new deploy is always
// picked up while online; the cache is an offline fallback only. The earlier
// CACHE-FIRST app-shell strategy (with a static CACHE_NAME) pinned a stale
// bundle across deploys — browsers never saw sw.js change, so they kept
// serving outdated HTML/JS and surfaced runtime errors from old code. The
// cache name bump below flushes those stale caches once; network-first
// prevents recurrence. Stale-while-revalidate is kept for verify proofs (the
// genuinely offline-first feature).

const CACHE_NAME = "landguard-v2";
const PRECACHE_URLS = ["/", "/verify", "/manifest.json", "/favicon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)),
      ),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Stale-while-revalidate for verify proofs (offline-first verification).
  if (url.pathname.startsWith("/api/proxy/v1/anchors/title/")) {
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cached = await cache.match(request);
        const fetchAndUpdate = fetch(request)
          .then((resp) => {
            if (resp.ok) cache.put(request, resp.clone());
            return resp;
          })
          .catch(() => cached);
        return cached || fetchAndUpdate;
      }),
    );
    return;
  }

  // Network-first for same-origin: always prefer fresh so deploys roll out,
  // fall back to cache only when offline. Keep the precached shell URLs warm
  // by refreshing them in the background on each successful fetch.
  if (url.origin === self.location.origin) {
    event.respondWith(
      fetch(request)
        .then((resp) => {
          if (resp.ok && PRECACHE_URLS.includes(url.pathname)) {
            const copy = resp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return resp;
        })
        .catch(() =>
          caches.match(request).then((cached) => cached || caches.match("/")),
        ),
    );
  }
});

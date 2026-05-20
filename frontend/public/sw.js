// LandGuard offline-aware service worker — Workbox-free, hand-rolled for the
// prototype. Caches the verify shell + recent Merkle proofs so a citizen can
// verify a title from cache when their phone has no signal.

const CACHE_NAME = "landguard-v1";
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

  // Stale-while-revalidate for verify proofs.
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

  // Cache-first for static + same-origin app shell.
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request)),
    );
  }
});

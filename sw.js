// Offline shell for the installable app. Pages are network-first (fresh when online),
// static assets are served from cache and refreshed in the background, and songs
// always stream from the network (they use range requests and are large).
const CACHE = "ecu-links-v5";
const SHELL = [
  "./",
  "index.html",
  "assets/css/site.css",
  "assets/js/i18n.js",
  "assets/js/player.js",
  "assets/js/motion.js",
  "assets/js/features.js",
  "assets/fonts/sora-0.woff2",
  "assets/fonts/sora-1.woff2",
  "images/favicon.svg",
  "images/profile-320.webp",
  "images/profile-640.webp",
  "images/qr.svg",
  "images/covers/amor-por-aqui-amor-por-alla.jpg",
  "images/covers/my-life.jpg",
  "images/covers/millones-mas.jpg",
  "images/covers/entre-la-multitud-600.jpg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== location.origin || url.pathname.includes("/audio/")) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request).then((hit) => hit || caches.match("index.html")))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((hit) => {
      const network = fetch(request).then((response) => {
        if (response.ok) caches.open(CACHE).then((cache) => cache.put(request, response.clone()));
        return response;
      }).catch(() => hit);
      return hit || network;
    })
  );
});

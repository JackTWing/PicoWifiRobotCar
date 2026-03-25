const CACHE_VERSION = "robot-shell-v1";
const STATIC_ASSETS = [
  "./dashboard.html",
  "./dashboard.css",
  "./dashboard.js",
  "./manifest.webmanifest",
  "./offline.html",
  "./icons/icon-192.svg",
  "./icons/icon-512.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_VERSION)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Never cache command/control calls. Always use network for live robot control.
  if (url.pathname.startsWith("/cmd/")) {
    event.respondWith(fetch(request));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(CACHE_VERSION);
        return cache.match("./offline.html");
      })
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }

      return fetch(request).then((networkResponse) => {
        if (request.method !== "GET") {
          return networkResponse;
        }

        const destination = request.destination;
        const isStaticAsset = ["style", "script", "image", "manifest", "font"].includes(destination);

        if (isStaticAsset) {
          const copy = networkResponse.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
        }

        return networkResponse;
      });
    })
  );
});

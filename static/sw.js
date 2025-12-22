const CACHE_NAME = 'offranel-cache-v1';
const urlsToCache = ['/', '/static/css/style.css']; // Ajoute tes fichiers principaux

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
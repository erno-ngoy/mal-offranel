const CACHE_NAME = 'offranel-cache-v1';
const urlsToCache = ['/', '/static/css/style.css']; // Ajoute tes fichiers principaux

// INSTALLATION : Mise en cache des fichiers de base
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

// FETCH : Stratégie de cache (Cache first, then network)
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});

/* --- AJOUT : GESTION DES NOTIFICATIONS PUSH --- */

// Écoute les notifications envoyées par le serveur (Admin action)
self.addEventListener('push', function(event) {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body,
            icon: '/static/img/image.png', // Ton logo orange
            badge: '/static/img/image.png',
            vibrate: [100, 50, 100],
            data: {
                url: data.url || '/' // Redirection au clic
            }
        };

        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});

// Gère le clic sur la notification
self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    );
});

/* --- AJOUT : NETTOYAGE DU VIEUX CACHE --- */
self.addEventListener('activate', event => {
    const cacheWhitelist = [CACHE_NAME];
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheWhitelist.indexOf(cacheName) === -1) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});
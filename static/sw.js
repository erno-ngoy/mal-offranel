const CACHE_NAME = 'offranel-cache-v1';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/img/image.png'
];

// INSTALLATION : Mise en cache des fichiers de base
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
  self.skipWaiting(); // Force la mise à jour immédiate du Service Worker
});

// FETCH : Stratégie de cache (Cache first, then network)
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});

/* --- AJOUT : GESTION DES NOTIFICATIONS PUSH (ALERTES TÉLÉPHONE) --- */

// Écoute les notifications envoyées par le serveur (Admin action)
self.addEventListener('push', function(event) {
    if (event.data) {
        let data = {};
        try {
            data = event.data.json();
        } catch (e) {
            // Si le serveur envoie du texte brut au lieu de JSON
            data = { title: "OFFRANEL 🍊", body: event.data.text() };
        }

        const options = {
            body: data.body || "Nouvel arrivage disponible !",
            icon: '/static/img/image.png', // Logo de l'alerte
            badge: '/static/img/image.png', // Petit icône dans la barre d'état
            vibrate: [200, 100, 200, 100, 200], // Séquence de vibration
            tag: 'new-product-alert', // Évite les doublons d'alertes
            renotify: true,
            data: {
                url: data.url || '/' // Redirection au clic
            },
            actions: [
                { action: 'open', title: 'Voir le produit 🛍️' },
                { action: 'close', title: 'Fermer' }
            ]
        };

        event.waitUntil(
            self.registration.showNotification(data.title || "OFFRANEL 🍊", options)
        );
    }
});

// Gère le clic sur la notification
self.addEventListener('notificationclick', function(event) {
    event.notification.close();

    // Si l'utilisateur clique sur "Voir le produit" ou sur la notif elle-même
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            // Si le site est déjà ouvert, on le met au premier plan
            for (let i = 0; i < clientList.length; i++) {
                let client = clientList[i];
                if (client.url === '/' && 'focus' in client) {
                    return client.focus();
                }
            }
            // Sinon on ouvre une nouvelle fenêtre
            if (clients.openWindow) {
                return clients.openWindow(event.notification.data.url);
            }
        })
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
        }).then(() => self.clients.claim()) // Prend le contrôle des pages immédiatement
    );
});
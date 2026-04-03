const CACHE_NAME = 'ntp-dash-v3';
const ASSETS_TO_CACHE =[
    '/',
    '/static/tailwindcss.js',
    '/static/dashboard.js',
    '/static/images/ntp-dashboard-logo.png',
    '/manifest.json'
];

// Install event: Cache the static files
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
    self.skipWaiting();
});

// Activate event: remove old caches so users receive updated JS/HTML assets
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => Promise.all(
            keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
        ))
    );
    self.clients.claim();
});

self.addEventListener('message', event => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

// Fetch event: Serve cached files, but ALWAYS fetch fresh data from the API
self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') {
        return;
    }

    const url = new URL(event.request.url);

    // Only manage same-origin requests.
    if (url.origin !== self.location.origin) {
        return;
    }

    // We NEVER want to cache the live time/GPS data APIs
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // For navigations (HTML), prefer network so UI/JS updates arrive quickly.
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => caches.match('/'))
        );
        return;
    }

    // Stale-while-revalidate for static assets keeps app responsive while refreshing cache in background.
    if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.json') {
        event.respondWith(
            caches.match(event.request).then(cached => {
                const networkFetch = fetch(event.request)
                    .then(response => {
                        if (response && response.ok) {
                            const responseCopy = response.clone();
                            caches.open(CACHE_NAME).then(cache => cache.put(event.request, responseCopy));
                        }
                        return response;
                    })
                    .catch(() => cached);

                return cached || networkFetch;
            })
        );
        return;
    }
    
    // Fallback strategy for any other same-origin GET request.
    event.respondWith(
        fetch(event.request).catch(() => {
            return caches.match(event.request);
        })
    );
});

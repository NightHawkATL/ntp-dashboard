const CACHE_NAME = 'ntp-dash-v2';
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

// Fetch event: Serve cached files, but ALWAYS fetch fresh data from the API
self.addEventListener('fetch', event => {
    // We NEVER want to cache the live time/GPS data APIs
    if (event.request.url.includes('/api/')) {
        return; 
    }

    // For navigations (HTML), prefer network so UI/JS updates arrive quickly.
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => caches.match('/'))
        );
        return;
    }
    
    // For everything else (HTML, images), serve from cache if available
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});

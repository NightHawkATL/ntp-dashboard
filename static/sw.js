const CACHE_NAME = 'ntp-dash-v1';
const ASSETS_TO_CACHE =[
    '/',
    '/static/tailwindcss.js',
    '/static/dashboard.js',
    '/static/images/logo.png',
    '/manifest.json'
];

// Install event: Cache the static files
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

// Fetch event: Serve cached files, but ALWAYS fetch fresh data from the API
self.addEventListener('fetch', event => {
    // We NEVER want to cache the live time/GPS data APIs
    if (event.request.url.includes('/api/')) {
        return; 
    }
    
    // For everything else (HTML, images), serve from cache if available
    event.respondWith(
        caches.match(event.request).then(response => {
            return response || fetch(event.request);
        })
    );
});

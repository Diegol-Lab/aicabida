// AiCabida Service Worker — Cache First strategy
const CACHE = 'aicabida-v42';

const PRECACHE = [
  '/',
  '/index.html',
  '/manifest.json',
  '/data/normas_prc.json',
  '/data/dotacion_estacionamientos.json',
  '/data/PRC_Bulnes.geojson',
  '/data/PRC_ElCarmen.geojson',
  '/data/PRC_Laja.geojson',
  '/data/PRC_Lebu.geojson',
  '/data/PRC_Penco.geojson',
  '/data/PRC_Tome.geojson',
  '/data/PRC_Yumbel.geojson',
  '/data/PRC_Yungay.geojson',
  '/data/PRC_Macul.geojson',
  '/data/PRC_LoBarnechea.geojson',
  '/data/PRC_Curanilahue.geojson',
  // CDN: Leaflet
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css',
  'https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js',
  // CDN: Turf
  'https://unpkg.com/@turf/turf@6/turf.min.js',
  // CDN: jsPDF
  'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
  // Fonts
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'
];

// Install: pre-cache app shell + data
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(cache => {
      return Promise.allSettled(
        PRECACHE.map(url => cache.add(url).catch(() => {}))
      );
    }).then(() => self.skipWaiting())
  );
});

// Activate: clean old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: Cache First for static assets & data, Network First for tiles
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // ESRI satellite tiles → Network with cache fallback
  if (url.hostname.includes('arcgisonline.com')) {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Everything else → Cache First
  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(res => {
        if (res && res.status === 200) {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return res;
      }).catch(() => {});
    })
  );
});

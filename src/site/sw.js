/* Gezichten Vervagen — service worker (install-as-app + offline use)
 *
 * Only registered when the tool is served over HTTPS; the portable copy never uses it.
 * It caches the tool's OWN files so the installed app also works offline.
 * It never contacts any other server and never sees photos (they are not network requests).
 *
 * Strategy: network-first with a short timeout, cache as fallback. Online users always
 * get the newest version (cheap thanks to HTTP revalidation); offline users get the cached one.
 */
const VERSION = '__VERSION__';
const PREFIX = 'gezichten-vervagen-';
const CACHE = PREFIX + VERSION;
const ASSETS = ['./', 'manifest.webmanifest', 'icons/icon.svg', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/icon-maskable-512.png', 'icons/apple-touch-icon.png'];
const TIMEOUT_MS = 4000;

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith(PREFIX) && k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function withTimeout(promise, ms) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('timeout')), ms);
    promise.then(v => { clearTimeout(t); resolve(v); }, e => { clearTimeout(t); reject(e); });
  });
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE);
  const key = request.mode === 'navigate' ? './' : request;
  try {
    const response = await withTimeout(fetch(request), TIMEOUT_MS);
    if (response.ok && response.type === 'basic') {
      // skip rewriting the ~9 MB page into the cache when it has not changed
      const cached = await cache.match(key);
      const etag = response.headers.get('etag'), lm = response.headers.get('last-modified');
      const same = cached && ((etag && cached.headers.get('etag') === etag) || (!etag && lm && cached.headers.get('last-modified') === lm));
      if (!same) await cache.put(key, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await cache.match(key, { ignoreSearch: true });
    if (cached) return cached;
    throw err;
  }
}

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(networkFirst(req));
});

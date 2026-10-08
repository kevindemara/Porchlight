/* Porchlight keeps recordings, API data and account state out of offline caches. */
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()))
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()))
self.addEventListener('fetch', event => {
  if (event.request.mode !== 'navigate') return
  const url = new URL(event.request.url)
  if (url.origin !== self.location.origin) return
  event.respondWith(fetch(event.request).catch(() => new Response(
    '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Porchlight unavailable</title><body><main><h1>Porchlight is unavailable</h1><p>The PC must be awake and reachable to save recordings, analyze activity or send alerts.</p><p>This screen contains no cached recordings or account information.</p><p><a href="/">Try again</a></p></main></body></html>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'Content-Security-Policy': "default-src 'none'; base-uri 'none'; frame-ancestors 'none'", 'X-Content-Type-Options': 'nosniff' } },
  )))
})

self.addEventListener('push', event => {
  event.waitUntil((async () => {
    let payload
    try { payload = event.data?.json() } catch { return }
    if (!payload || typeof payload.body !== 'string' || payload.body.length > 500 ||
        typeof payload.tag !== 'string' || payload.tag.length > 100 ||
        !Number.isFinite(payload.expires_at) || payload.expires_at * 1000 < Date.now()) return
    const id = typeof payload.event_id === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(payload.event_id) ? payload.event_id : null
    await self.registration.showNotification(id ? 'Porchlight activity' : 'Porchlight test', {
      body: payload.body, tag: payload.tag, icon: '/icons/porchlight-v3-192.png',
      data: { event_id: id }, renotify: false,
    })
  })())
})

self.addEventListener('notificationclick', event => {
  event.notification.close()
  const id = event.notification.data?.event_id
  const valid = typeof id === 'string' && /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(id)
  const target = new URL(valid ? `/#activity?event=${encodeURIComponent(id)}` : '/#notifications', self.location.origin)
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    const existing = windows.find(client => new URL(client.url).origin === self.location.origin)
    if (existing) { await existing.navigate(target.href); await existing.focus() }
    else await self.clients.openWindow(target.href)
  })())
})

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

const WORKER_VERSION = 'previews-v2'
const UUID = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i
self.addEventListener('message', event => {
  if (event.data?.type === 'PORCHLIGHT_VERSION') event.ports[0]?.postMessage(WORKER_VERSION)
})

async function notificationImage(id) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 10000)
  try {
    const response = await fetch(`/api/v1/events/${id}/notification-thumbnail`, {
      credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal,
    })
    if (response.status === 401 || response.status === 403) return { preview: 'unauthorized' }
    if (!response.ok) return { preview: 'unreachable' }
    if (response.headers.get('content-type')?.split(';')[0] !== 'image/jpeg' || !response.body) return { preview: 'invalid' }
    const reader = response.body.getReader()
    const chunks = []
    let total = 0
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      total += value.length
      if (total > 512 * 1024) { await reader.cancel(); return { preview: 'invalid' } }
      chunks.push(value)
    }
    const bytes = new Uint8Array(total)
    let offset = 0
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length }
    if (bytes[0] !== 0xff || bytes[1] !== 0xd8) return { preview: 'invalid' }
    let binary = ''
    for (let index = 0; index < bytes.length; index += 8192) binary += String.fromCharCode(...bytes.subarray(index, index + 8192))
    return { preview: 'ready', image: `data:image/jpeg;base64,${btoa(binary)}` }
  } catch { return { preview: controller.signal.aborted ? 'timeout' : 'unreachable' } }
  finally { clearTimeout(timer) }
}

async function receipt(payload, outcome, preview) {
  if (typeof payload.delivery_id !== 'string' || !UUID.test(payload.delivery_id)) return
  // Authenticated, CSRF-protected status only. No description/image/subscription.
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 3000)
  try {
    const session = await fetch('/api/v1/auth/session', { credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal })
    if (!session.ok) return
    const { csrf_token } = await session.json()
    if (typeof csrf_token !== 'string') return
    await fetch(`/api/v1/push/deliveries/${payload.delivery_id}/receipt`, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf_token },
      body: JSON.stringify({ worker_version: WORKER_VERSION, outcome, preview,
        descriptive: payload.body !== 'New camera activity. Open Porchlight to review the recording.' }),
    })
  } catch { /* The notification must not depend on a reachable home server. */ }
  finally { clearTimeout(timer) }
}

// Serialize competing pushes: a slower initial preview must not overwrite a
// newer description. Across worker lifetimes compare metadata on the OS item.
let notificationWork = Promise.resolve()
self.addEventListener('push', event => {
  notificationWork = notificationWork.catch(() => {}).then(async () => {
    let payload
    try { payload = event.data?.json() } catch { return }
    if (!payload || typeof payload.body !== 'string' || payload.body.length > 500 ||
        typeof payload.tag !== 'string' || payload.tag.length > 100 ||
        !Number.isFinite(payload.expires_at) || payload.expires_at * 1000 < Date.now()) return
    const id = typeof payload.event_id === 'string' && UUID.test(payload.event_id) ? payload.event_id : null
    const issued = Number.isFinite(payload.issued_at) ? payload.issued_at : 0
    const present = await self.registration.getNotifications({ tag: payload.tag })
    if (present.some(item => (item.data?.issued_at ?? 0) > issued)) {
      await receipt(payload, 'superseded', 'not_requested'); return
    }
    if (payload.update_only === true && !present.length) {
      await receipt(payload, 'dismissed', 'not_requested'); return
    }
    const options = {
      body: payload.body, tag: payload.tag, icon: '/icons/porchlight-v4-192.png',
      badge: '/icons/porchlight-badge-v4-96.png',
      data: { event_id: id, issued_at: issued }, renotify: false, ...(payload.silent === true ? { silent: true } : {}),
    }
    // Submit the text immediately; private-network thumbnail latency must not
    // hold up the initial alert or its new description.
    try { await self.registration.showNotification(id ? 'Porchlight activity' : 'Porchlight test', options) }
    catch { await receipt(payload, 'failed', 'not_requested'); return }
    const preview = id && payload.thumbnail === true ? await notificationImage(id) : { preview: 'not_requested' }
    if (preview.image && payload.expires_at * 1000 >= Date.now()) {
      const displayed = await self.registration.getNotifications({ tag: payload.tag })
      if (!displayed.length) { await receipt(payload, 'dismissed', preview.preview); return }
      if (displayed.some(item => (item.data?.issued_at ?? 0) > issued)) {
        await receipt(payload, 'superseded', preview.preview); return
      }
      try {
        await self.registration.showNotification('Porchlight activity', { ...options, image: preview.image, silent: true })
      } catch { preview.preview = 'display_rejected' } // The descriptive text is already submitted.
    }
    await receipt(payload, 'submitted', preview.preview)
  })
  event.waitUntil(notificationWork)
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

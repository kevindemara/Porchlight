import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

test('descriptive activity push opens its exact protected recording in a new or existing window', async ({ page, context }, info) => {
  const directory = mkdtempSync(join(tmpdir(), 'porchlight-push-recording-'))
  const video = join(directory, 'generated.mp4')
  execFileSync(join(process.env.LOCALAPPDATA!, 'Porchlight/tools/ffmpeg/bin/ffmpeg.exe'), ['-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=c=orange:s=320x240:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', video])
  try {
    await enterWorkspace(page)
    const session = await (await page.request.get('/api/v1/auth/session')).json()
    const imported = await page.request.post('/api/v1/imports', { headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token, 'Content-Type': 'video/mp4' }, data: readFileSync(video) })
    expect(imported.status()).toBe(201)
    const recording = await imported.json()
    await page.evaluate(async () => { await navigator.serviceWorker.ready })
    // Navigate under the now-active worker before testing background fetches.
    await page.reload()
    await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true)
    const worker = context.serviceWorkers()[0]
    // Simulate the OS click, using the real worker handler and real recording API.
    const opened = await worker.evaluate(async ({ id, body }) => {
      const scope = globalThis as unknown as {
        location: { origin: string }
        registration: { showNotification: (title: string, options: NotificationOptions) => Promise<void> }
        clients: { matchAll: () => Promise<unknown[]>; openWindow: (url: string) => Promise<unknown> }
        dispatchEvent: (event: Event) => boolean
      }
      let options: NotificationOptions = {}
      const targets: string[] = []
      let focused = 0, closed = 0
      const originals = { show: scope.registration.showNotification, match: scope.clients.matchAll, open: scope.clients.openWindow }
      async function emit(type: string, properties: Record<string, unknown>) {
        const promises: Promise<unknown>[] = []
        const event = new Event(type)
        for (const [key, value] of Object.entries(properties)) Object.defineProperty(event, key, { value })
        Object.defineProperty(event, 'waitUntil', { value: (promise: Promise<unknown>) => { promises.push(promise) } })
        scope.dispatchEvent(event)
        await Promise.all(promises)
      }
      try {
        scope.registration.showNotification = async (_title, value) => { options = value }
        await emit('push', { data: { json: () => ({ event_id: id, body, tag: 'synthetic-description', expires_at: Date.now() / 1000 + 60, url: 'https://example.invalid' }) } })
        const notification = { data: options.data, close: () => { closed++ } }
        scope.clients.matchAll = async () => []
        scope.clients.openWindow = async url => { targets.push(url); return null }
        await emit('notificationclick', { notification })
        scope.clients.matchAll = async () => [{ url: `${scope.location.origin}/#live`, navigate: async (url: string) => { targets.push(url) }, focus: async () => { focused++ } }]
        await emit('notificationclick', { notification })
        return { targets, focused, closed, body: options.body }
      } finally {
        scope.registration.showNotification = originals.show
        scope.clients.matchAll = originals.match
        scope.clients.openWindow = originals.open
      }
    }, { id: recording.id, body: 'A white car is visible.' })
    const target = `${new URL(page.url()).origin}/#activity?event=${recording.id}`
    expect(opened).toEqual({ targets: [target, target], focused: 1, closed: 2, body: 'A white car is visible.' })
    await page.goto(target)
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Close recording' })).toBeVisible()
    await expect.poll(() => page.locator('dialog video').evaluate((element: HTMLVideoElement) => element.readyState)).toBeGreaterThanOrEqual(2)
    await page.screenshot({ path: info.outputPath('notification-recording.png'), fullPage: true })
  } finally { rmSync(directory, { recursive: true, force: true }) }
})

test('push previews authenticate with no open window, fall back without login and do not resurrect dismissed face alerts', async ({ page, context }) => {
  await enterWorkspace(page)
  const session = await (await page.request.get('/api/v1/auth/session')).json()
  // The JPEG is a generated blue fixture, never camera media.
  const directory = mkdtempSync(join(tmpdir(), 'porchlight-preview-'))
  const jpeg = join(directory, 'generated.jpg')
  try {
    execFileSync(join(process.env.LOCALAPPDATA!, 'Porchlight/tools/ffmpeg/bin/ffmpeg.exe'), ['-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'color=c=blue:s=320x240', '-frames:v', '1', '-y', jpeg])
    const imported = await page.request.post('/api/v1/imports', { headers: { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token, 'Content-Type': 'image/jpeg' }, data: readFileSync(jpeg) })
    expect(imported.status()).toBe(201)
    const recording = await imported.json()
    await page.evaluate(async () => { await navigator.serviceWorker.ready })
    await page.reload()
    await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true)
    const worker = context.serviceWorkers()[0]
    const receiptStatuses: number[] = []
    context.on('response', response => {
      if (new URL(response.url()).pathname === `/api/v1/push/deliveries/${recording.id}/receipt`) receiptStatuses.push(response.status())
    })
    async function send(update: boolean, present: boolean) {
      return worker.evaluate(async ({ id, update, present }) => {
        const scope = globalThis as unknown as {
          registration: { showNotification: (title: string, options: NotificationOptions & { image?: string }) => Promise<void>; getNotifications: () => Promise<Notification[]> }
          dispatchEvent: (event: Event) => boolean
        }
        const original = { show: scope.registration.showNotification, get: scope.registration.getNotifications }
        const shown: (NotificationOptions & { image?: string })[] = []
        try {
          scope.registration.showNotification = async (_title, options) => { shown.push(options) }
          scope.registration.getNotifications = async () => present || shown.length ? [ { data: shown.at(-1)?.data } as Notification ] : []
          const promises: Promise<unknown>[] = []
          const event = new Event('push')
          Object.defineProperty(event, 'data', { value: { json: () => ({ event_id: id, delivery_id: id, body: update ? 'Alex exits through the doorway.' : 'A person is visible.', tag: 'same-recording', thumbnail: true, update_only: update, silent: update, expires_at: Date.now() / 1000 + 60, image: 'https://example.invalid/unsafe.jpg' }) } })
          Object.defineProperty(event, 'waitUntil', { value: (promise: Promise<unknown>) => { promises.push(promise) } })
          scope.dispatchEvent(event)
          await Promise.all(promises)
          return shown.map(options => ({ image: options.image?.startsWith('data:image/jpeg;base64,/9j/'), body: options.body, tag: options.tag, silent: options.silent, renotify: options.renotify }))
        } finally { scope.registration.showNotification = original.show; scope.registration.getNotifications = original.get }
      }, { id: recording.id, update, present })
    }
    expect(await send(false, false)).toEqual([{ image: undefined, body: 'A person is visible.', tag: 'same-recording', silent: undefined, renotify: false }, { image: true, body: 'A person is visible.', tag: 'same-recording', silent: true, renotify: false }])
    expect(await send(true, true)).toEqual([{ image: undefined, body: 'Alex exits through the doorway.', tag: 'same-recording', silent: true, renotify: false }, { image: true, body: 'Alex exits through the doorway.', tag: 'same-recording', silent: true, renotify: false }])
    expect(await send(true, false)).toEqual([])
    // A synthetic delivery ID intentionally has no database row. A real 404
    // proves the receipt passed Host/Origin, session and CSRF protection.
    await expect.poll(() => receiptStatuses).toEqual([404, 404, 404])
    expect(await page.evaluate(async () => (await caches.keys()).length)).toBe(0)
    await page.close()
    expect(context.pages()).toHaveLength(0)
    expect(await send(false, false)).toEqual([{ image: undefined, body: 'A person is visible.', tag: 'same-recording', silent: undefined, renotify: false }, { image: true, body: 'A person is visible.', tag: 'same-recording', silent: true, renotify: false }])
    await expect.poll(() => receiptStatuses).toEqual([404, 404, 404, 404])
    await context.clearCookies()
    const denied = await send(false, false)
    expect(denied).toHaveLength(1)
    expect(denied[0].image).toBeUndefined()
    expect(denied[0].body).toBe('A person is visible.')
    expect(receiptStatuses).toEqual([404, 404, 404, 404]) // Signed-out worker cannot submit receipts.
    expect(await worker.evaluate(async () => (await caches.keys()).length)).toBe(0)
  } finally { rmSync(directory, { recursive: true, force: true }) }
})

test('installed-app launch headers load the shell on first and service-worker-controlled reopen', async ({ page, context, baseURL }) => {
  const target = new URL('/', baseURL).href
  let launches = 0
  let workerLaunches = 0
  let metadata = { 'sec-fetch-mode': 'navigate', 'sec-fetch-dest': 'document' }
  // Emulate launcher metadata only on the document. Assets and API calls use
  // normal browser headers and the production backend, not mocked responses.
  await context.route(target, async route => {
    launches++
    if (route.request().serviceWorker()) workerLaunches++
    await route.continue({ headers: { ...await route.request().allHeaders(),
      'sec-fetch-site': 'cross-site', ...metadata,
      origin: 'android-app://org.chromium.webapk.synthetic',
    } })
  })
  const response = await page.goto(target)
  expect(response?.status()).toBe(200)
  expect(launches).toBe(1)
  await expect(page.getByRole('heading', { name: /Sign in to Porchlight|Make yourself at home/ })).toBeVisible()
  await page.evaluate(async () => { await navigator.serviceWorker.ready })
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true)
  for (const mode of ['same-origin', 'cors', 'navigate']) {
    metadata = { 'sec-fetch-mode': mode, 'sec-fetch-dest': 'empty' }
    const reopened = await context.newPage()
    try {
      const response = await reopened.goto(target)
      expect(response?.status()).toBe(200)
      await expect(reopened.getByRole('heading', { name: /Sign in to Porchlight|Make yourself at home/ })).toBeVisible()
      expect((await reopened.request.get('/api/v1/auth/session', { headers: { origin: 'null', 'sec-fetch-site': 'cross-site' } })).status()).toBe(403)
    } finally { await reopened.close() }
  }
  expect(launches).toBe(4)
  expect(workerLaunches).toBe(3)
})

test('install prompt is retained before settings, requested only on click, and consumed once', async ({ page }, info) => {
  await enterWorkspace(page)
  const writes: string[] = []
  page.on('request', request => { if (request.url().includes('/api/v1/') && !['GET', 'HEAD'].includes(request.method())) writes.push(new URL(request.url()).pathname) })
  // Browser-specific install UI is simulated; this does not prove phone installation.
  const suppressed = await page.evaluate(() => {
    const event = new Event('beforeinstallprompt', { cancelable: true })
    const calls: string[] = []
    Object.defineProperty(window, 'syntheticInstallCalls', { configurable: true, value: calls })
    Object.defineProperty(event, 'prompt', { value: async () => { calls.push('prompt') } })
    Object.defineProperty(event, 'userChoice', { value: Promise.resolve({ outcome: 'dismissed' }) })
    window.dispatchEvent(event)
    return event.defaultPrevented
  })
  expect(suppressed).toBe(true)
  await page.getByRole('link', { name: 'Settings', exact: true }).click()
  await page.getByRole('button', { name: 'Notifications', exact: true }).click()
  const install = page.getByRole('button', { name: 'Install Porchlight', exact: true })
  await expect(install).toBeVisible()
  expect(await page.evaluate(() => (window as unknown as { syntheticInstallCalls: string[] }).syntheticInstallCalls)).toEqual([])
  await page.evaluate(() => { document.documentElement.dataset.theme = 'dark' })
  await page.screenshot({ path: info.outputPath('phone-install.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await install.click()
  await expect(page.getByText('Installation cancelled. You can still use Porchlight in the browser.', { exact: true })).toBeVisible()
  await expect(install).toHaveCount(0)
  await page.getByRole('link', { name: 'Live View', exact: true }).click()
  await page.getByRole('link', { name: 'Settings', exact: true }).click()
  await page.getByRole('button', { name: 'Notifications', exact: true }).click()
  await expect(install).toHaveCount(0)
  await page.evaluate(() => {
    const event = new Event('beforeinstallprompt', { cancelable: true })
    Object.defineProperty(event, 'prompt', { value: async () => { (window as unknown as { syntheticInstallCalls: string[] }).syntheticInstallCalls.push('accepted') } })
    Object.defineProperty(event, 'userChoice', { value: Promise.resolve({ outcome: 'accepted' }) })
    window.dispatchEvent(event)
  })
  await install.click()
  await expect(page.getByText('Installation requested. Look for the Porchlight icon on your home screen.', { exact: true })).toBeVisible()
  await page.evaluate(() => { window.dispatchEvent(new Event('appinstalled')) })
  await expect(page.getByText('Porchlight is installed. Open its home-screen icon for app mode.', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => (window as unknown as { syntheticInstallCalls: string[] }).syntheticInstallCalls)).toEqual(['prompt', 'accepted'])
  expect(writes).toEqual([]) // Installation does not pair a browser or enable rules.
})

test('browser shell has an install manifest and shows honest offline state without private caches', async ({ page, context }) => {
  await page.goto('/')
  const favicon = await page.request.get('/favicon-v4.ico')
  expect(favicon.ok()).toBe(true)
  expect(favicon.headers()['content-type']).toContain('image/x-icon')
  const ico = await favicon.body()
  expect(ico.readUInt16LE(2)).toBe(1)
  expect(ico.readUInt16LE(4)).toBe(3)
  for (const entry of [0, 1, 2]) {
    const offset = ico.readUInt32LE(6 + entry * 16 + 12)
    expect(ico.subarray(offset + 1, offset + 4).toString()).toBe('PNG')
  }
  for (const icon of await page.locator('link[rel="icon"], link[rel="apple-touch-icon"]').all()) {
    const response = await page.request.get((await icon.getAttribute('href'))!)
    expect(response.ok()).toBe(true)
    expect(response.headers()['content-type']).toMatch(/image\//)
  }
  const mark = await page.request.get('/icons/porchlight-mark-v4.png')
  expect(mark.ok()).toBe(true)
  const markBytes = await mark.body()
  expect(markBytes.readUInt32BE(16)).toBe(256)
  expect(markBytes[25]).toBe(6) // RGBA PNG preserves the owner-provided transparency.
  const badge = await page.request.get('/icons/porchlight-badge-v4-96.png')
  expect(badge.ok()).toBe(true)
  expect(badge.headers()['content-type']).toContain('image/png')
  const badgeBytes = await badge.body()
  expect(badgeBytes.readUInt32BE(16)).toBe(96)
  expect(badgeBytes.readUInt32BE(20)).toBe(96)
  expect(badgeBytes[25]).toBe(6)
  const manifest = await (await page.request.get('/manifest.webmanifest')).json()
  expect(manifest.name).toBe('Porchlight')
  expect(manifest.display).toBe('standalone')
  expect(manifest.icons.map((icon: { sizes: string }) => icon.sizes)).toEqual(['192x192', '512x512', '512x512'])
  for (const icon of manifest.icons) {
    const iconResponse = await page.request.get(icon.src)
    expect(iconResponse.ok()).toBe(true)
    const iconBytes = await iconResponse.body()
    expect(iconBytes.subarray(1, 4).toString()).toBe('PNG')
    const width = iconBytes.readUInt32BE(16), height = iconBytes.readUInt32BE(20)
    expect(height).toBe(width)
    expect(icon.sizes).toBe(`${width}x${height}`)
  }
  await page.evaluate(async () => { await navigator.serviceWorker.ready })
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true)
  expect(await page.evaluate(async () => (await caches.keys()).length)).toBe(0)
  await context.setOffline(true)
  await page.goto('/?offline-test=synthetic')
  await expect(page.getByRole('heading', { name: 'Porchlight is unavailable', exact: true })).toBeVisible()
  await expect(page.getByText(/The PC must be awake and reachable/)).toBeVisible()
  expect(await page.evaluate(async () => (await caches.keys()).length)).toBe(0)
  await context.setOffline(false)
  await page.getByRole('link', { name: 'Try again', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Sign in to Porchlight|Make yourself at home/ })).toBeVisible()
  const worker = context.serviceWorkers()[0]
  const shown = await worker.evaluate(async () => {
    const scope = globalThis as unknown as { registration: { showNotification: (title: string, options: NotificationOptions) => Promise<void> }; dispatchEvent: (event: Event) => boolean }
    const notifications: { title: string; options: NotificationOptions }[] = []
    Object.defineProperty(scope.registration, 'showNotification', { configurable: true, value: async (title: string, options: NotificationOptions) => { notifications.push({ title, options }) } })
    async function emit(data: unknown) {
      const promises: Promise<unknown>[] = []
      const event = new Event('push')
      Object.defineProperty(event, 'data', { value: { json: () => data } })
      Object.defineProperty(event, 'waitUntil', { value: (promise: Promise<unknown>) => { promises.push(promise) } })
      scope.dispatchEvent(event)
      await Promise.all(promises)
    }
    await emit({ body: 'Expired synthetic message', tag: 'old', expires_at: 0 })
    await emit({ body: 'Synthetic generic activity', tag: 'synthetic-tag', expires_at: Date.now() / 1000 + 60, event_id: 'c96a2ac2-5314-4a44-b1f8-4108036591b2', title: 'Unchecked title', url: 'https://example.invalid', image: 'https://example.invalid/private.jpg' })
    return notifications
  })
  expect(shown).toHaveLength(1)
  expect(shown[0].title).toBe('Porchlight activity')
  expect(shown[0].options.data).toEqual({ event_id: 'c96a2ac2-5314-4a44-b1f8-4108036591b2', issued_at: 0 })
  expect(shown[0].options).not.toHaveProperty('image')
  expect(shown[0].options.renotify).toBe(false)
  expect(shown[0].options.icon).toBe(manifest.icons[0].src)
  expect(shown[0].options.badge).toBe('/icons/porchlight-badge-v4-96.png')
})


test('worker serializes slow previews, keeps the newest description and falls back if image display is rejected', async ({ page, context }, info) => {
  await enterWorkspace(page)
  await page.evaluate(async () => { await navigator.serviceWorker.ready })
  await page.reload()
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true)
  const worker = context.serviceWorkers()[0]
  const result = await worker.evaluate(async () => {
    const scope = globalThis as unknown as {
      registration: { getNotifications: () => Promise<{ data: Record<string, unknown> }[]>; showNotification: (title: string, options: NotificationOptions & { image?: string }) => Promise<void> }
      dispatchEvent: (event: Event) => boolean
      fetch: typeof fetch
    }
    const original = { fetch: scope.fetch, get: scope.registration.getNotifications, show: scope.registration.showNotification }
    const receipts: unknown[] = [], shown: string[] = []
    let current: Record<string, unknown> | null = null
    let release!: () => void
    const gate = new Promise<void>(resolve => { release = resolve })
    let imageCalls = 0, rejected = 0
    try {
      scope.fetch = async (input, init) => {
        const path = String(input)
        if (path.endsWith('notification-thumbnail')) {
          if (++imageCalls === 1) await gate
          return new Response(new Uint8Array([255, 216, 255, 217]), { headers: { 'Content-Type': 'image/jpeg' } })
        }
        if (path.endsWith('/auth/session')) return Response.json({ csrf_token: 'synthetic-csrf' })
        receipts.push(JSON.parse(String(init?.body)))
        if ((init?.headers as Record<string, string>)['X-CSRF-Token'] !== 'synthetic-csrf') throw new Error('Missing CSRF')
        return new Response(null, { status: 204 })
      }
      scope.registration.getNotifications = async () => current ? [{ data: current }] : []
      scope.registration.showNotification = async (_title, options) => {
        if (options.image) { rejected++; throw new TypeError('Synthetic unsupported image') }
        current = options.data; shown.push(options.body!)
      }
      function emit(body: string, issued: number, thumbnail: boolean) {
        const promises: Promise<unknown>[] = []
        const event = new Event('push')
        Object.defineProperty(event, 'data', { value: { json: () => ({
          event_id: '00000000-0000-4000-8000-000000000001', delivery_id: '00000000-0000-4000-8000-000000000002',
          body, tag: 'one-recording', thumbnail, issued_at: issued, expires_at: Date.now()/1000+120,
        }) } })
        Object.defineProperty(event, 'waitUntil', { value: (promise: Promise<unknown>) => { promises.push(promise) } })
        scope.dispatchEvent(event); return Promise.all(promises)
      }
      const initial = emit('New camera activity. Open Porchlight to review the recording.', 1, true)
      const analysis = emit('Alex exits through the doorway.', 2, true)
      await new Promise(resolve => setTimeout(resolve, 50))
      const beforePreview = shown.slice()
      release(); await Promise.all([initial, analysis])
      await emit('New camera activity. Open Porchlight to review the recording.', 1, false)
      return { shown, receipts, rejected, beforePreview }
    } finally { scope.fetch = original.fetch; scope.registration.getNotifications = original.get; scope.registration.showNotification = original.show }
  })
  expect(result.shown).toEqual(['New camera activity. Open Porchlight to review the recording.', 'Alex exits through the doorway.'])
  expect(result.beforePreview).toEqual(['New camera activity. Open Porchlight to review the recording.'])
  expect(result.rejected).toBe(2)
  expect(result.receipts).toEqual([
    { worker_version: 'previews-v2', outcome: 'submitted', preview: 'display_rejected', descriptive: false },
    { worker_version: 'previews-v2', outcome: 'submitted', preview: 'display_rejected', descriptive: true },
    { worker_version: 'previews-v2', outcome: 'superseded', preview: 'not_requested', descriptive: false },
  ])
  // Native protected-media/security routes are exercised above; this fixture
  // supplies a configured origin solely for checking the phone status UI.
  await page.route('**/api/v1/push', route => route.fulfill({ json: {
    dependency_ready: true, configured: true, public_origin: new URL(page.url()).origin,
    public_key: 'synthetic', message: 'Synthetic paired browser', devices: [],
    deliveries: [{ id: 'synthetic', device_id: 'synthetic', event_id: null,
      status: 'transport_accepted', created_at: new Date().toISOString(), safe_error: null,
      browser_receipt: { worker_version: 'previews-v2', outcome: 'submitted', preview: 'ready', descriptive: true } }],
  } }))
  await page.goto('/#settings?section=notifications')
  await page.getByRole('button', { name: 'Refresh phone notifications' }).click()
  await expect(page.getByText('Notification worker: previews-v2.', { exact: true })).toBeVisible()
  await page.getByText('Delivery history', { exact: true }).click()
  await expect(page.getByText(/Phone worker submitted · description received · preview ready/)).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('phone-push-receipt.png'), fullPage: true })

})

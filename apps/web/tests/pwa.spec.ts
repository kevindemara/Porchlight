import { test, expect } from '@playwright/test'

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
  expect(shown[0].options.data).toEqual({ event_id: 'c96a2ac2-5314-4a44-b1f8-4108036591b2' })
  expect(shown[0].options).not.toHaveProperty('image')
  expect(shown[0].options.renotify).toBe(false)
  expect(shown[0].options.icon).toBe(manifest.icons[0].src)
})

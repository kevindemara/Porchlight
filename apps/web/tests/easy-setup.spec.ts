import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('AI setup offers a real skip path on a small PC without automatic installs or inference', async ({ page }, info) => {
  await enterWorkspace(page)
  const mutations: string[] = []
  page.on('request', request => { if (request.url().includes('/api/v1/') && request.method() !== 'GET') mutations.push(new URL(request.url()).pathname) })
  await page.route('**/api/v1/setup/ai-readiness', route => route.fulfill({ json: {
    ram_bytes: 8 * 1024 ** 3, cpu_threads: 4, gpu_memory_bytes: null, recommendation: 'skip',
    suggested_model: null, suggested_workload: 'light', message: 'Start without AI to leave memory for Windows and the archive.',
  } }))
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Settings' }).click()
  await page.getByRole('button', { name: 'Open setup guide', exact: true }).click()
  await page.getByRole('navigation', { name: 'Setup steps' }).getByRole('button', { name: 'Local AI' }).click()
  await page.getByRole('button', { name: 'Check this PC for AI' }).click()
  await expect(page.getByText('Start without AI to leave memory for Windows and the archive.', { exact: true })).toBeVisible()
  await expect(page.getByText('8.0 GiB RAM', { exact: false })).toBeVisible()
  await expect(page.getByRole('checkbox', { name: 'Analyze new recordings automatically' })).not.toBeChecked()
  expect(mutations).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('ai-optional.png'), fullPage: true })
  await page.getByRole('button', { name: 'Use Porchlight without AI' }).click()
  await expect(page.getByRole('heading', { name: 'Phone access and permissions' })).toBeVisible()
  const settings = await (await page.request.get('/api/v1/settings')).json()
  expect(settings.ai_enabled).toBe(false)
  const faces = await (await page.request.get('/api/v1/face-detection/status')).json()
  expect(faces.enabled).toBe(false)
  expect(mutations).toEqual(['/api/v1/face-detection/control'])
  await page.getByRole('button', { name: 'Skip for now', exact: true }).click()
  await expect(page.getByText('Automatic AI: paused', { exact: false })).toBeVisible()
})

test('phone wizard distinguishes configured HTTPS from real remote and push acceptance', async ({ page }, info) => {
  await enterWorkspace(page)
  await page.route('**/api/v1/push', route => route.fulfill({ json: {
    dependency_ready: false, configured: false, public_origin: 'https://porchlight.example.com',
    public_key: null, message: 'Optional push packages are unavailable.', devices: [], deliveries: [],
  } }))
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Settings' }).click()
  await page.getByRole('button', { name: 'Notifications', exact: true }).click()
  await expect(page.getByText('HTTPS address configured', { exact: true })).toBeVisible()
  await expect(page.getByText('Configured does not mean reachable from cellular.', { exact: false })).toBeVisible()
  await page.getByText('Connect without a phone VPN', { exact: true }).click()
  await expect(page.getByRole('link', { name: 'Download phone connection guide' })).toHaveAttribute('href', '/api/v1/setup/guides/phone')
  await expect(page.getByText('Cloudflare applies video-delivery restrictions', { exact: false })).toBeVisible()
  await page.getByText('Direct home HTTPS — no phone VPN', { exact: true }).click()
  await expect(page.getByRole('link', { name: 'Download direct HTTPS guide' })).toHaveAttribute('href', '/api/v1/setup/guides/direct-https')
  await page.getByText('Cloudflare private tunnel — optional backup', { exact: true }).click()
  await expect(page.getByRole('link', { name: 'Download private tunnel backup guide' })).toHaveAttribute('href', '/api/v1/setup/guides/cloudflare-backup')
  await expect(page.getByRole('button', { name: 'Create local push keys' })).toBeDisabled()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('phone-connection.png'), fullPage: true })
})

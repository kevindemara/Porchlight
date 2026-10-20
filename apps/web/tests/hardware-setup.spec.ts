import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('hardware wizard saves guidance, preserves source gates and survives reopening', async ({ page }, info) => {
  await enterWorkspace(page)
  const initial = await (await page.request.get('/api/v1/settings')).json()
  const writes: string[] = []
  page.on('request', request => { if (request.url().includes('/api/v1/') && !['GET', 'HEAD'].includes(request.method())) writes.push(new URL(request.url()).pathname) })
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Settings' }).click()
  await page.getByRole('button', { name: 'Open setup guide', exact: true }).click()
  await page.getByRole('navigation', { name: 'Setup steps' }).getByRole('button', { name: 'Recording source' }).click()
  const module = page.getByLabel('Sync Module type', { exact: true })
  await expect(module).toHaveValue('unknown')
  for (const [value, guidance] of [
    ['core', 'No removable-storage recording'], ['original', 'No removable-storage recording'],
    ['sync_module_2', 'USB drive'], ['xr', 'microSD card'], ['xr_plus', 'microSD card'],
    ['none', 'No module storage'], ['mixed', 'Check each system separately'],
  ]) {
    await module.selectOption(value)
    await expect(page.getByText(guidance, { exact: true })).toBeVisible()
  }
  expect(writes).toEqual([])
  await module.selectOption('xr_plus')
  await page.getByLabel('Camera setup', { exact: true }).selectOption('mixed')
  await expect(page.getByRole('button', { name: 'Sync local recordings', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: 'Save hardware choice' }).click()
  await expect(page.getByText('Hardware choice saved. Recording access is still checked separately.', { exact: true })).toBeVisible()
  const saved = await (await page.request.get('/api/v1/settings')).json()
  expect(saved.blink_module_setup).toBe('xr_plus')
  expect(saved.blink_camera_setup).toBe('mixed')
  expect(saved.blink_entitlement).toBe(initial.blink_entitlement)
  expect(saved.ai_enabled).toBe(initial.ai_enabled)
  expect(writes).toEqual(['/api/v1/settings'])
  await page.getByText('Local recording or cloud backup?', { exact: true }).click()
  await expect(page.getByText('Legacy XT, XT2 and Indoor', { exact: false })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('hardware-guidance.png'), fullPage: true })
  await page.getByRole('navigation', { name: 'Setup steps' }).getByRole('button', { name: 'Review', exact: true }).click()
  await expect(page.getByText('Sync Module XR+. This saved choice guides setup; it does not verify hardware or recording access.', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Close guide' }).click()
  await page.reload()
  await expect(page.getByLabel('Sync Module type', { exact: true })).toHaveValue('xr_plus')
  await expect(page.getByLabel('Camera setup', { exact: true })).toHaveValue('mixed')
  await expect(page.getByRole('button', { name: 'Sync local recordings', exact: true })).toBeDisabled()
})

test('failed hardware save remains unsaved and never changes entitlement or storage', async ({ page }) => {
  await enterWorkspace(page)
  const initial = await (await page.request.get('/api/v1/settings')).json()
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Settings' }).click()
  await page.getByLabel('Sync Module type', { exact: true }).selectOption('sync_module_2')
  await page.route('**/api/v1/settings', route => route.request().method() === 'PUT'
    ? route.fulfill({ status: 409, json: { code: 'SETTINGS_CHANGED', message: 'Settings changed in another tab. Reload first.', retryable: false } })
    : route.continue())
  await page.getByRole('button', { name: 'Save hardware choice' }).click()
  await expect(page.getByText('Settings changed in another tab. Reload first.', { exact: true })).toBeVisible()
  const saved = await (await page.request.get('/api/v1/settings')).json()
  expect(saved.blink_module_setup).toBe(initial.blink_module_setup)
  expect(saved.blink_entitlement).toBe(initial.blink_entitlement)
  await expect(page.getByRole('button', { name: 'Sync local recordings', exact: true })).toBeDisabled()
})

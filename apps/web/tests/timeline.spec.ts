import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('timeline groups local dates, preserves newest-first paging and explains coverage', async ({ page }, testInfo) => {
  const event = (index: number, captured: string | null, discovered: string) => ({
    id: `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`, media_id: '00000000-0000-4000-8000-999999999999',
    source_type: 'manual_import', captured_at: captured, discovered_at: discovered, timestamp_quality: captured ? 'valid' : 'unknown',
    analysis_status: 'analyzed', summary: `Synthetic timeline ${index}`, note: '', favourite: false, duration_seconds: 1,
    object_categories: ['vehicle', 'unknown'], historical: index === 2,
  })
  const items = [event(1, '2026-10-07T02:00:00Z', '2026-10-07T04:00:00Z'), event(2, '2026-10-06T15:00:00Z', '2026-10-07T04:00:00Z'), event(3, null, '2026-10-05T16:00:00Z'), event(4, '2026-10-04T16:00:00Z', '2026-10-07T04:00:00Z')]
  await page.route('**/api/v1/events?*', route => route.fulfill({ json: new URL(route.request().url()).searchParams.has('cursor') ? { items: items.slice(3), next_cursor: null } : { items: items.slice(0, 3), next_cursor: items[2].id } }))
  await page.route('**/api/v1/health', async route => {
    const health = await (await route.fetch()).json()
    await route.fulfill({ json: { ...health, checks: [{ key: 'listing', label: 'Clip listing', state: 'disabled', message: 'Synthetic paused listing.', queued: 0, running: 0, needs_attention: 0 }] } })
  })
  await enterWorkspace(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Activity', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Tuesday, October 6, 2026', exact: true })).toHaveCount(1)
  await expect(page.getByRole('heading', { name: 'Monday, October 5, 2026', exact: true })).toBeVisible()
  expect(await page.locator('.event-copy h3').allTextContents()).toEqual(['Synthetic timeline 1', 'Synthetic timeline 2', 'Synthetic timeline 3'])
  await expect(page.getByRole('complementary', { name: 'Recording coverage' })).toContainText('Recording sync is paused.')
  await expect(page.getByText('Historical import · alerts paused', { exact: true })).toBeVisible()
  await expect(page.locator('.object-chips').first()).toContainText('vehicle')
  await expect(page.getByText(/recording time unknown/)).toBeVisible()
  await page.getByRole('button', { name: 'Load more recordings', exact: true }).click()
  await expect(page.locator('.event-copy h3')).toHaveText(items.map(item => item.summary))
  await expect(page.getByRole('heading', { name: 'Sunday, October 4, 2026', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Load more recordings', exact: true })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('timeline.png'), fullPage: true })
})

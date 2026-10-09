import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('Activity shows a saved name, keeps unknown people generic and retains the original description', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await enterWorkspace(page)
  const original = 'A person moves from left to right. A black car is visible. A white car is visible.'
  const named = original.replace('A person', 'Alex')
  const common = { source_type: 'manual_import', captured_at: '2026-10-08T12:00:00Z', discovered_at: '2026-10-08T12:01:00Z', timestamp_quality: 'manual', analysis_status: 'analyzed', ai_summary: original, corrected_summary: null, labels_source: 'ai', favourite: false, note: '', duration_seconds: 10, media_type: 'video/mp4', historical: false, object_categories: ['person', 'vehicle'] }
  const known = { ...common, id: 'cd720d5d-0ea2-40a5-8a26-a7b5e0cfe23d', media_id: 'a20712ca-942a-4b24-8128-eb2aa3d9e34b', summary: named, recognized_people: ['Alex'] }
  const unknown = { ...common, id: '9726fdd2-a5dd-4f3a-a7ef-53d01cfcb479', media_id: '49449b8c-55ae-4cba-a1c5-de8e5fc9ad16', summary: original, recognized_people: [] }
  // Synthetic display fixture; backend tests separately verify read-time substitution.
  await page.route('**/api/v1/events?*', route => route.fulfill({ json: { items: [known, unknown], next_cursor: null } }))
  await page.route(`**/api/v1/events/${known.id}`, route => route.fulfill({ json: known }))
  await page.route(`**/api/v1/events/${known.id}/analysis`, route => route.fulfill({ json: null }))
  await page.route(`**/api/v1/events/${known.id}/faces`, route => route.fulfill({ json: { status: 'not_requested', report: null, people: {} } }))
  await page.getByRole('link', { name: 'Activity', exact: true }).click()
  await expect(page.getByRole('heading', { name: named, exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: original, exact: true })).toBeVisible()
  await expect(page.locator('.event-card').first().getByText('Possible face match: Alex', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('activity-named-summary.png'), fullPage: true })
  await page.getByRole('button', { name: new RegExp('Alex moves from left to right') }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText(named, { exact: true })).toBeVisible()
  await dialog.getByText('Original AI description', { exact: true }).click()
  await expect(dialog.getByText(original, { exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath('activity-named-detail.png') })
  expect(errors).toEqual([])
})

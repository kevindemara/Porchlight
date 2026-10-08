import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('long archive windows variable rows and preserves paging, keyboard focus and resize', async ({ page }, testInfo) => {
  const events = Array.from({ length: 180 }, (_, index) => ({
    id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, '0')}`, media_id: '00000000-0000-4000-8000-999999999999',
    source_type: 'manual_import', media_type: 'image/jpeg', captured_at: new Date(Date.UTC(2026, 9, 7, 16) - index * 60_000).toISOString(),
    discovered_at: '2026-10-07T16:00:00Z', timestamp_quality: 'valid', analysis_status: 'not_analyzed',
    summary: `Window fixture ${String(index + 1).padStart(3, '0')}`, note: index % 7 === 0 ? 'A deliberately longer synthetic note. '.repeat(12) : '',
    favourite: false, duration_seconds: 0, object_categories: index % 3 === 0 ? ['vehicle', 'package', 'unknown'] : [],
  }))
  await page.route('**/api/v1/events?*', route => {
    const cursor = new URL(route.request().url()).searchParams.get('cursor')
    const start = cursor ? events.findIndex(event => event.id === cursor) + 1 : 0
    const items = events.slice(start, start + 30)
    return route.fulfill({ json: { items, next_cursor: start + 30 < events.length ? items.at(-1)!.id : null } })
  })
  await page.route(/\/api\/v1\/events\/[^/]+$/, route => {
    const index = events.findIndex(event => route.request().url().endsWith(event.id))
    if (route.request().method() === 'DELETE') { events.splice(index, 1); return route.fulfill({ status: 204 }) }
    return route.fulfill({ json: events[index] })
  })
  await page.route(/\/api\/v1\/events\/[^/]+\/match\?/, route => route.fulfill({ json: events.find(event => route.request().url().includes(event.id)) ?? null }))
  await page.route(/\/api\/v1\/events\/[^/]+\/annotation$/, route => {
    const event = events.find(event => route.request().url().includes(event.id))!
    Object.assign(event, route.request().postDataJSON())
    return route.fulfill({ json: event })
  })
  await page.route(/\/api\/v1\/events\/[^/]+\/analysis$/, route => route.fulfill({ json: null }))
  await enterWorkspace(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Activity', exact: true }).click()
  const list = page.getByRole('list', { name: 'Saved recordings', exact: true })
  await expect(list).toHaveAttribute('data-window-total', '30')
  for (let count = 60; count <= 180; count += 30) {
    await page.getByRole('button', { name: 'Load more recordings', exact: true }).click()
    await expect(list).toHaveAttribute('data-window-total', String(count))
  }
  await expect.poll(() => list.locator('.event-card').count()).toBeLessThan(45)
  await list.evaluate(element => window.scrollTo(0, element.getBoundingClientRect().top + window.scrollY))
  await expect(page.getByRole('heading', { name: 'Window fixture 001', exact: true })).toBeVisible()
  await expect.poll(() => list.locator('.event-card').count()).toBeLessThan(45)
  const last = list.locator('.window-row').last()
  const position = Number(await last.getAttribute('aria-posinset'))
  await last.locator('.event-card').focus()
  await page.keyboard.press('Tab')
  const following = list.locator(`.window-row[aria-posinset="${position + 1}"] .event-card`)
  await expect(following).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(list.locator(`.window-row[aria-posinset="${position}"] .event-card`)).toBeFocused()
  const original = page.viewportSize()!
  await page.setViewportSize({ width: original.width < 640 ? 900 : 390, height: original.height })
  await expect(list.locator(`.window-row[aria-posinset="${position}"] .event-card`)).toBeFocused()
  await expect.poll(() => list.locator('.event-card').count()).toBeLessThan(45)
  await page.setViewportSize(original)
  await list.evaluate(element => window.scrollTo(0, element.getBoundingClientRect().top + window.scrollY + element.getBoundingClientRect().height / 2))
  await expect.poll(async () => Number(await list.getAttribute('data-window-start'))).toBeGreaterThan(50)
  const visible = await list.locator('.window-row').evaluateAll(rows => {
    const row = rows.find(element => { const rect = element.getBoundingClientRect(); return rect.top >= 0 && rect.bottom <= innerHeight })
    return Number(row?.getAttribute('aria-posinset'))
  })
  expect(visible).toBeGreaterThan(50)
  const selected = list.locator(`.window-row[aria-posinset="${visible}"] .event-card`)
  await selected.click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByLabel('Your notes', { exact: true }).fill('Edited in the middle of a long archive')
  await page.getByRole('button', { name: 'Save changes', exact: true }).click()
  await expect(page.getByText('Saved.', { exact: true })).toBeVisible()
  await expect(list).toHaveAttribute('data-window-total', '180')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(selected).toBeFocused()
  await expect(list).toHaveAttribute('data-window-total', '180')
  await expect(selected).toContainText('Edited in the middle of a long archive')
  await selected.click()
  await page.getByRole('button', { name: 'Delete local recording', exact: true }).click()
  await page.getByRole('button', { name: 'Delete local recording', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(list).toHaveAttribute('data-window-total', '179')
  await expect.poll(() => list.locator('.event-card').count()).toBeLessThan(45)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('long-history-window.png') })
})

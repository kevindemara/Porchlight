import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('older inbox page survives refresh and can return to latest', async ({ page }) => {
  await enterWorkspace(page)
  await page.clock.install()
  const cursor = '0d50d4fb-e995-4e40-a04c-dda8a793828a'
  const requests: string[] = []
  await page.route(/\/api\/v1\/notifications(?:\?.*)?$/, async route => {
    const query = new URL(route.request().url()).searchParams.get('cursor')
    requests.push(query ?? 'latest')
    await route.fulfill({ json: {
      unread: 31, snoozed_until: null, next_cursor: query ? null : cursor,
      items: [{ id: query ? 'c83cf3b5-f94e-451e-906c-ecff9cf975b5' : cursor,
        event_id: null, title: query ? 'Older synthetic alert' : 'Latest synthetic alert',
        body: 'Synthetic paging fixture', created_at: '2026-10-07T10:00:00Z', read: true }],
    } })
  })
  await page.getByRole('link', { name: 'Notifications', exact: true }).click()
  await expect(page.getByText('Latest synthetic alert', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Older notifications', exact: true }).click()
  await expect(page.getByText('Older synthetic alert', { exact: true })).toBeVisible()
  const before = requests.filter(value => value === cursor).length
  await page.clock.fastForward(11_000)
  await expect.poll(() => requests.filter(value => value === cursor).length).toBeGreaterThan(before)
  await expect(page.getByText('Older synthetic alert', { exact: true })).toBeVisible()
  await expect(page.getByText('Latest synthetic alert', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Latest notifications', exact: true }).click()
  await expect(page.getByText('Latest synthetic alert', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

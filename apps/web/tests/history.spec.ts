import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('history range and stop/resume controls preserve independent ordinary sync', async ({ page }, testInfo) => {
  let state = 'not_started'
  let days: number | null = null
  const actions: string[] = []
  const status = () => ({ enabled: true, discovered: 5, archived: 5, pending: 0, failed: 0,
    state: 'ready', message: 'Synthetic ordinary sync.', history: { state, days, discovered: 2, archived: 1, pending: 1, failed: 0 } })
  await page.route('**/api/v1/integrations/blink/recordings', route => route.fulfill({ json: status() }))
  await page.route('**/api/v1/integrations/blink/history', route => {
    const body = route.request().postDataJSON()
    actions.push(body.action)
    if (body.action === 'start') { days = body.days; state = 'scanning' }
    else state = body.action === 'pause' ? 'paused' : 'downloading'
    return route.fulfill({ status: 202, json: status() })
  })
  await enterWorkspace(page)
  await page.getByRole('navigation').getByRole('link', { name: 'Settings', exact: true }).click()
  await page.getByText('Retrieve older cloud recordings', { exact: true }).click()
  await page.getByLabel('History range').selectOption('0')
  await page.getByRole('button', { name: 'Retrieve selected history' }).click()
  await expect(page.getByText('History: scanning', { exact: false })).toBeVisible()
  expect(days).toBe(0)
  await page.getByRole('button', { name: 'Stop history retrieval' }).click()
  await expect(page.getByRole('button', { name: 'Resume history' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Pause sync', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Resume history' }).click()
  await expect(page.getByText('History: downloading', { exact: false })).toBeVisible()
  expect(actions).toEqual(['start', 'pause', 'resume'])
  await page.reload()
  await page.getByText('Retrieve older cloud recordings', { exact: true }).click()
  await expect(page.getByText('History: downloading', { exact: false })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('history-settings.png'), fullPage: true })
})

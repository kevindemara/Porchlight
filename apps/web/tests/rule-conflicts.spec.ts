import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('rule edit and deletion conflicts preserve drafts until explicit saved-version review', async ({ page }, info) => {
  await enterWorkspace(page)
  await page.getByRole('link', { name: 'Notifications', exact: true }).click()
  await page.getByLabel('Rule name', { exact: true }).fill('Synthetic conflict rule')
  await page.getByRole('button', { name: 'Save rule', exact: true }).click()
  await expect(page.getByText('Rule saved.', { exact: true })).toBeVisible()
  const fetchRules = async () => (await page.request.get('/api/v1/notification-rules')).json()
  let frozen = await fetchRules()
  let freezeList = true
  await page.route('**/api/v1/notification-rules', route => route.request().method() === 'GET' && freezeList ? route.fulfill({ json: frozen }) : route.continue())
  let saved = frozen.find((rule: { definition: { name: string } }) => rule.definition.name === 'Synthetic conflict rule')
  const path = `/api/v1/notification-rules/${saved.id}`
  const session = await (await page.request.get('/api/v1/auth/session')).json()
  const headers = { Origin: new URL(page.url()).origin, 'X-CSRF-Token': session.csrf_token }
  await page.route(`**${path}*`, route => { freezeList = false; return route.continue() })
  await page.locator('.diagnostic-row').filter({ hasText: 'Synthetic conflict rule' }).getByRole('button', { name: 'Edit rule', exact: true }).click()
  await page.getByLabel('Rule name', { exact: true }).fill('My unsaved synthetic draft')
  const newer = await page.request.put(path, { headers, data: { expected_revision: saved.revision, definition: { ...saved.definition, name: 'Newer synthetic browser rule' } } })
  expect(newer.status()).toBe(200)
  saved = await newer.json()
  const conflict = page.waitForResponse(response => response.url().endsWith(path) && response.request().method() === 'PUT' && response.status() === 409)
  await page.getByRole('button', { name: 'Save rule', exact: true }).click()
  await conflict
  await expect(page.getByRole('group', { name: 'Rule draft conflict' })).toBeVisible()
  await expect(page.getByLabel('Rule name', { exact: true })).toHaveValue('My unsaved synthetic draft')
  await expect(page.getByRole('button', { name: 'Save rule', exact: true })).toBeDisabled()
  expect((await fetchRules()).find((rule: { id: string }) => rule.id === saved.id).definition.name).toBe('Newer synthetic browser rule')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath('rule-draft-conflict.png'), fullPage: true })
  await page.getByRole('button', { name: 'Reload saved rule', exact: true }).click()
  await expect(page.getByLabel('Rule name', { exact: true })).toHaveValue('Newer synthetic browser rule')
  await page.getByLabel('Rule name', { exact: true }).fill('Reviewed synthetic rule')
  await page.getByRole('button', { name: 'Save rule', exact: true }).click()
  await expect(page.getByText('Rule saved.', { exact: true })).toBeVisible()
  frozen = await fetchRules(); freezeList = true
  saved = frozen.find((rule: { id: string }) => rule.id === saved.id)
  await page.locator('.diagnostic-row').filter({ hasText: 'Reviewed synthetic rule' }).getByRole('button', { name: 'Delete rule', exact: true }).click()
  expect((await page.request.put(path, { headers, data: { expected_revision: saved.revision, definition: { ...saved.definition, name: 'Rule updated before deletion' } } })).status()).toBe(200)
  const staleDelete = page.waitForResponse(response => response.url().includes(path) && response.request().method() === 'DELETE' && response.status() === 409)
  await page.getByRole('button', { name: 'Confirm delete rule', exact: true }).click()
  await staleDelete
  await page.getByRole('button', { name: 'Review latest rule for deletion', exact: true }).click()
  await expect(page.getByRole('group', { name: 'Confirm rule deletion' })).toContainText('Rule updated before deletion')
  await page.getByRole('button', { name: 'Confirm delete rule', exact: true }).click()
  await expect(page.getByText('Rule deleted.', { exact: true })).toBeVisible()
  expect((await fetchRules()).some((rule: { id: string }) => rule.id === saved.id)).toBe(false)
})

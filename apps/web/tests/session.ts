import { expect, type Cookie, type Page } from '@playwright/test'

// Synthetic session cookies live only in this isolated worker's memory. Reuse the
// real session API rather than disabling the production eight-logins/minute limit.
const sessions = new Map<string, Cookie[]>()

export async function enterWorkspace(page: Page) {
  await page.goto('/')
  const origin = new URL(page.url()).origin
  const cached = sessions.get(origin)
  if (cached) {
    await page.context().addCookies(cached)
    if ((await page.request.get('/api/v1/auth/session')).ok()) {
      await page.reload()
      await expect(page.getByRole('heading', { name: 'Live View', exact: true })).toBeVisible()
      return
    }
    sessions.delete(origin)
    await page.reload()
  }
  await page.getByLabel('Username', { exact: true }).fill('synthetic_browser')
  await page.getByLabel('Password', { exact: true }).fill('synthetic-browser-passphrase')
  if (await page.getByLabel('Confirm password').count()) await page.getByLabel('Confirm password').fill('synthetic-browser-passphrase')
  await page.getByRole('button', { name: /Create workspace|^Sign in$/ }).click()
  // New owners land in the real setup guide. Most journeys begin on Live View.
  await expect(page.getByRole('heading', { name: 'Live View', exact: true }).or(page.getByRole('heading', { name: 'Set up Porchlight', exact: true }))).toBeVisible()
  if (await page.getByRole('button', { name: 'Close guide', exact: true }).isVisible()) {
    await page.getByRole('button', { name: 'Close guide', exact: true }).click()
    await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Live View', exact: true }).click()
  }
  await expect(page.getByRole('heading', { name: 'Live View', exact: true })).toBeVisible()
  sessions.set(origin, await page.context().cookies())
}

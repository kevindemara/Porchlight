import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('workspace actions stay reachable without a separate top bar', async ({ page }, testInfo) => {
  await enterWorkspace(page)
  await expect(page.locator('.topbar')).toHaveCount(0)
  await expect(page.getByText('Your home, at a glance', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Local app', { exact: true })).toHaveCount(0)
  await expect(page.getByText('YOUR WORKSPACE', { exact: true })).toHaveCount(0)
  const notifications = page.getByRole('link', { name: 'Notifications', exact: true })
  const signOut = page.getByRole('button', { name: 'Sign out of Porchlight', exact: true })
  await expect(notifications).toHaveCount(1)
  await expect(signOut).toHaveCount(1)
  await expect(notifications).toBeVisible()
  await expect(signOut).toBeVisible()
  const heading = await page.getByRole('heading', { name: 'Live View', exact: true }).boundingBox()
  expect(heading!.y).toBeLessThan(40)
  if (page.viewportSize()!.width <= 600) {
    await expect(page.locator('.sidebar-footer')).toBeHidden()
    const actions = await page.locator('.mobile-workspace-actions').boundingBox()
    expect(actions!.y).toBeLessThan(40)
    const bell = await notifications.locator('svg').boundingBox()
    const exit = await signOut.locator('svg').boundingBox()
    expect(Math.abs(bell!.y - exit!.y)).toBeLessThanOrEqual(1)
    for (const control of [notifications, signOut]) {
      const box = await control.boundingBox()
      expect(box!.width).toBeGreaterThanOrEqual(44)
      expect(box!.height).toBeGreaterThanOrEqual(44)
    }
  } else {
    await expect(page.locator('.mobile-workspace-actions')).toBeHidden()
    const badge = await page.getByText('Local workspace', { exact: true }).boundingBox()
    for (const control of [notifications, signOut]) {
      const box = await control.boundingBox()
      expect(box!.y + box!.height).toBeLessThan(badge!.y)
    }
  }
  await page.screenshot({ path: testInfo.outputPath('compact-workspace.png'), fullPage: true })
  const theme = await page.locator('html').getAttribute('data-theme')
  await page.evaluate(() => { document.documentElement.dataset.theme = 'dark' })
  await page.screenshot({ path: testInfo.outputPath('compact-workspace-dark.png'), fullPage: true })
  await page.evaluate(value => { if (value) document.documentElement.dataset.theme = value; else delete document.documentElement.dataset.theme }, theme)
  await notifications.click()
  await expect(page.getByRole('heading', { name: 'Notifications', exact: true, level: 1 })).toBeVisible()
  await expect(notifications).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('link', { name: 'Notification settings', exact: true })).toBeVisible()
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Activity', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Import recording', exact: true })).toBeVisible()
  await expect(page.getByText('YOUR WORKSPACE', { exact: true })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('compact-activity.png'), fullPage: true })
  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Faces', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Facial recognition', exact: true, level: 1 })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await expect(notifications).toBeVisible()
  await signOut.click()
  await expect(page.getByRole('heading', { name: 'Sign in to Porchlight', exact: true })).toBeVisible()
})

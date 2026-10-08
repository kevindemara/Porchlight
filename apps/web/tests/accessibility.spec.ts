import { test, expect } from '@playwright/test'
import { enterWorkspace } from './session'

test('keyboard skip link focuses the current page without changing its route or filters', async ({ page }) => {
  await enterWorkspace(page)
  for (const name of ['Activity', 'Search', 'Settings', 'Library', 'Live view', 'Cameras']) {
    const link = page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name, exact: true })
    await link.click()
    await expect(link).toHaveAttribute('aria-current', 'page')
    await expect(page.getByRole('heading', { name, exact: true, level: 1 })).toBeVisible()
    for (const role of ['button', 'textbox', 'combobox', 'checkbox'] as const) {
      for (const control of await page.getByRole(role).all()) {
        await expect(control).toHaveAccessibleName(/\S/)
      }
    }
    if (name === 'Activity') await page.getByRole('textbox', { name: 'Search recordings' }).fill('keyboard fixture')
    const route = page.url()
    const skip = page.getByRole('link', { name: 'Skip to content', exact: true })
    await skip.focus()
    await expect(skip).toBeFocused()
    await expect(skip).toBeVisible()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(route)
    await expect(page.getByRole('main')).toBeFocused()
    await expect(link).toHaveAttribute('aria-current', 'page')
    if (name === 'Activity') await expect(page.getByRole('textbox', { name: 'Search recordings' })).toHaveValue('keyboard fixture')
  }
})

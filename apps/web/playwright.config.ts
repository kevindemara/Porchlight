import { defineConfig } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { tmpdir } from 'node:os'
import { resolve, join } from 'node:path'

const profile = join(tmpdir(), `porchlight-e2e-${randomUUID()}`)
const viewports = [
  { name: 'desktop', port: 18765, width: 1440, height: 1000, mobile: false },
  { name: 'phone', port: 18766, width: 390, height: 844, mobile: true },
  { name: 'small-phone', port: 18767, width: 360, height: 800, mobile: true },
  { name: 'tablet', port: 18768, width: 768, height: 1024, mobile: false },
]
export default defineConfig({
  testDir: './tests',
  workers: 1,
  fullyParallel: false,
  timeout: 30_000,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:18765', channel: 'msedge', headless: true, trace: 'off' },
  // Each profile retains the production login throttle and single-process lock.
  webServer: viewports.map(viewport => ({
    command: `"${resolve('../../.venv/Scripts/python.exe')}" -m porchlight`,
    url: `http://127.0.0.1:${viewport.port}/health/live`,
    timeout: 30_000,
    reuseExistingServer: false,
    env: { PORCHLIGHT_PORT: String(viewport.port), PORCHLIGHT_DATA_ROOT: join(profile, viewport.name) },
  })),
  projects: viewports.map(viewport => ({ name: viewport.name, use: {
    baseURL: `http://127.0.0.1:${viewport.port}`,
    viewport: { width: viewport.width, height: viewport.height },
    isMobile: viewport.mobile, hasTouch: viewport.mobile,
  } })),
})

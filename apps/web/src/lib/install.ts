type InstallPrompt = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}
type InstallState = { available: boolean; installed: boolean }

let state: InstallState = { available: false, installed: false }
let pendingPrompt: InstallPrompt | null = null
let initialized = false
const listeners = new Set<() => void>()

function update(next: InstallState) {
  if (state.available === next.available && state.installed === next.installed) return
  state = next
  listeners.forEach(listener => listener())
}

// Capture the browser event at startup, including before Settings is opened.
// One shared listener survives React StrictMode and component remounts.
export function initializeInstall() {
  if (initialized) return
  initialized = true
  const standalone = window.matchMedia('(display-mode: standalone)')
  const displayChanged = () => update({ ...state, installed: standalone.matches })
  displayChanged()
  standalone.addEventListener('change', displayChanged)
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault()
    pendingPrompt = event as InstallPrompt
    update({ available: true, installed: state.installed })
  })
  window.addEventListener('appinstalled', () => {
    pendingPrompt = null
    update({ available: false, installed: true })
  })
}

export const getInstallState = () => state
export function subscribeInstall(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export async function promptInstall(): Promise<'accepted' | 'dismissed' | 'unavailable'> {
  const prompt = pendingPrompt
  if (!prompt) return 'unavailable'
  pendingPrompt = null
  update({ ...state, available: false })
  // Called directly from the owner's click, preserving the browser user gesture.
  await prompt.prompt()
  return (await prompt.userChoice).outcome
}

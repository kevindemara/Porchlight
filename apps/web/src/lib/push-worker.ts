export const PUSH_WORKER_VERSION = 'previews-v2'

export async function refreshPushWorker(): Promise<string> {
  const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' })
  await registration.update()
  const worker = registration.installing ?? registration.waiting ?? registration.active
  if (!worker) throw new Error('Phone notification worker is unavailable. Keep the private connection on and try again.')
  if (worker.state !== 'activated') await new Promise<void>((resolve, reject) => {
    const finish = () => {
      if (worker.state === 'activated' || worker.state === 'redundant') {
        clearTimeout(timer); worker.removeEventListener('statechange', finish)
        if (worker.state === 'activated') resolve()
        else reject(new Error('Notification update was interrupted. Try again.'))
      }
    }
    const timer = setTimeout(() => { worker.removeEventListener('statechange', finish); reject(new Error('Notification update is taking longer than expected. Try again.')) }, 15000)
    worker.addEventListener('statechange', finish); finish()
  })
  return new Promise<string>((resolve, reject) => {
    const channel = new MessageChannel()
    const timer = setTimeout(() => { channel.port1.close(); reject(new Error('The old phone worker is still active. Close and reopen Porchlight, then refresh again.')) }, 3000)
    channel.port1.onmessage = event => {
      clearTimeout(timer); channel.port1.close()
      if (event.data === PUSH_WORKER_VERSION) resolve(event.data)
      else reject(new Error('The phone notification worker needs an update. Try refreshing again.'))
    }
    worker.postMessage({ type: 'PORCHLIGHT_VERSION' }, [channel.port2])
  })
}

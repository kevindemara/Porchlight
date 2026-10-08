import { useEffect, useRef } from 'react'

export type Topic = 'activity' | 'cameras' | 'settings' | 'notifications' | 'library' | 'health'
const topics = new Set<Topic>(['activity', 'cameras', 'settings', 'notifications', 'library', 'health'])
const eventName = 'porchlight:state-update'

export function onTopic(topic: Topic, callback: () => void) {
  const listener = (event: Event) => {
    const detail = (event as CustomEvent<Topic[]>).detail
    if (Array.isArray(detail) && detail.includes(topic)) callback()
  }
  window.addEventListener(eventName, listener)
  return () => window.removeEventListener(eventName, listener)
}

export function useStateUpdates(enabled: boolean, onChange: (topics: Topic[]) => void, onExpired: () => void) {
  const handlers = useRef({ onChange, onExpired })
  useEffect(() => { handlers.current = { onChange, onExpired } }, [onChange, onExpired])
  useEffect(() => {
    if (!enabled || !('EventSource' in window)) return
    const source = new EventSource('/api/v1/stream')
    let timer: number | undefined
    const pending = new Set<Topic>()
    const changed = (event: MessageEvent<string>) => {
      if (event.data.length > 4096) return
      try {
        const data: unknown = JSON.parse(event.data)
        if (!data || typeof data !== 'object' || !('topics' in data) || !Array.isArray(data.topics)) return
        for (const topic of data.topics) if (topics.has(topic as Topic)) pending.add(topic as Topic)
        if (!pending.size || timer !== undefined) return
        timer = window.setTimeout(() => {
          const update = [...pending]; pending.clear(); timer = undefined
          window.dispatchEvent(new CustomEvent<Topic[]>(eventName, { detail: update }))
          handlers.current.onChange(update)
        }, 500)
      } catch { /* Guarded polling remains available if a proxy sends an invalid event. */ }
    }
    source.addEventListener('change', changed)
    source.addEventListener('resync', changed)
    source.addEventListener('session_expired', () => { source.close(); handlers.current.onExpired() })
    return () => { source.close(); if (timer !== undefined) window.clearTimeout(timer) }
  }, [enabled])
}

import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'

const FULL_LIST_LIMIT = 80
const BUFFER = 700

function rowAt(offsets: number[], position: number) {
  let low = 0, high = offsets.length - 1
  while (low < high) {
    const middle = Math.ceil((low + high) / 2)
    if (offsets[middle] <= position) low = middle
    else high = middle - 1
  }
  return Math.min(low, offsets.length - 2)
}

/** Measured rows, native document scrolling and a bounded visible/keyboard window. */
export default function WindowedList({ keys, renderRow }: { keys: string[]; renderRow: (index: number) => ReactNode }) {
  const root = useRef<HTMLDivElement>(null)
  const nodes = useRef(new Map<string, HTMLDivElement>())
  const sizes = useRef(new Map<string, number>())
  const observer = useRef<ResizeObserver | null>(null)
  const anchor = useRef<{ key: string; within: number; scrollY: number } | null>(null)
  const frame = useRef(0)
  const width = useRef(0)
  const [measurement, measured] = useState(0)
  const [range, setRange] = useState({ start: 0, end: 12 })
  const [focused, setFocused] = useState<string | null>(null)
  const pendingFocus = useRef<string | null>(null)
  const offsets = useMemo(() => {
    const result = [0]
    for (const key of keys) result.push(result[result.length - 1] + (sizes.current.get(key) ?? 190))
    return result
  }, [keys, measurement])

  const locate = useCallback(() => {
    if (!root.current || !keys.length) return
    const top = root.current.getBoundingClientRect().top + window.scrollY
    const relative = Math.max(0, window.scrollY - top)
    const first = rowAt(offsets, relative)
    anchor.current = { key: keys[first], within: relative - offsets[first], scrollY: window.scrollY }
    const start = rowAt(offsets, Math.max(0, relative - BUFFER))
    const end = Math.min(keys.length, rowAt(offsets, relative + window.innerHeight + BUFFER) + 1)
    setRange(previous => previous.start === start && previous.end === end ? previous : { start, end })
  }, [keys, offsets])

  useLayoutEffect(() => {
    // Keep the same recording/pixel when measurements or appended pages change the geometry.
    const saved = anchor.current
    if (root.current && saved && keys.length > FULL_LIST_LIMIT && Math.abs(window.scrollY - saved.scrollY) <= 1) {
      const index = keys.indexOf(saved.key)
      const top = root.current.getBoundingClientRect().top + window.scrollY
      if (index >= 0 && window.scrollY >= top) {
        const within = Math.min(saved.within, offsets[index + 1] - offsets[index] - 1)
        window.scrollTo(0, top + offsets[index] + Math.max(0, within))
      }
    }
    locate()
  }, [keys, offsets, locate])

  useEffect(() => {
    const schedule = () => {
      if (!frame.current) frame.current = window.requestAnimationFrame(() => { frame.current = 0; locate() })
    }
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule, { passive: true })
    return () => { window.removeEventListener('scroll', schedule); window.removeEventListener('resize', schedule); window.cancelAnimationFrame(frame.current); frame.current = 0 }
  }, [locate])

  useLayoutEffect(() => {
    const resize = new ResizeObserver(entries => {
      let changed = false
      for (const entry of entries) {
        if (entry.target === root.current) {
          const nextWidth = Math.round(entry.contentRect.width)
          if (width.current && width.current !== nextWidth) { sizes.current.clear(); changed = true }
          width.current = nextWidth
        }
      }
      for (const entry of entries) {
        const element = entry.target as HTMLDivElement
        const key = element.dataset.windowKey
        if (!key) continue
        const height = Math.ceil(element.getBoundingClientRect().height)
        if (height > 0 && sizes.current.get(key) !== height) { sizes.current.set(key, height); changed = true }
      }
      if (changed) measured(value => value + 1)
    })
    observer.current = resize
    if (root.current) resize.observe(root.current)
    nodes.current.forEach(node => resize.observe(node))
    return () => { resize.disconnect(); observer.current = null }
  }, [])

  useEffect(() => {
    const present = new Set(keys)
    sizes.current.forEach((_, key) => { if (!present.has(key)) sizes.current.delete(key) })
  }, [keys])

  useLayoutEffect(() => {
    const key = pendingFocus.current
    if (!key) return
    const button = nodes.current.get(key)?.querySelector('button')
    if (button) { pendingFocus.current = null; button.focus({ preventScroll: true }); button.scrollIntoView({ block: 'nearest' }) }
  }, [focused])

  const full = keys.length <= FULL_LIST_LIMIT
  const start = full ? 0 : Math.min(range.start, Math.max(0, keys.length - 1))
  const end = full ? keys.length : Math.max(start + 1, Math.min(keys.length, range.end))
  const indexes = Array.from({ length: end - start }, (_, index) => start + index)
  const focusedIndex = focused ? keys.indexOf(focused) : -1
  if (focusedIndex >= 0 && !indexes.includes(focusedIndex)) indexes.push(focusedIndex)
  indexes.sort((left, right) => left - right)
  let previous = 0
  return <div ref={root} className="windowed-list" role="list" aria-label="Saved recordings" data-window-total={keys.length} data-window-start={start}
    onFocusCapture={event => { const key = (event.target as HTMLElement).closest<HTMLElement>('[data-window-key]')?.dataset.windowKey; if (key) setFocused(key) }}
    onKeyDown={event => {
      if (full || event.key !== 'Tab' || !(event.target as HTMLElement).closest('.event-card')) return
      const key = (event.target as HTMLElement).closest<HTMLElement>('[data-window-key]')?.dataset.windowKey
      const index = key ? keys.indexOf(key) : -1
      const next = index + (event.shiftKey ? -1 : 1)
      if (index >= 0 && next >= 0 && next < keys.length) {
        event.preventDefault(); pendingFocus.current = keys[next]; setFocused(keys[next])
      }
    }}>
    {indexes.map(index => {
      const gap = offsets[index] - previous
      previous = offsets[index + 1]
      return <Fragment key={keys[index]}>
        {gap > 0 && <div aria-hidden="true" className="window-spacer" style={{ height: gap }} />}
        <div role="listitem" aria-posinset={index + 1} aria-setsize={keys.length} className="window-row" data-window-key={keys[index]} ref={element => {
          const old = nodes.current.get(keys[index]); if (old) observer.current?.unobserve(old)
          if (element) { nodes.current.set(keys[index], element); observer.current?.observe(element) }
          else nodes.current.delete(keys[index])
        }}>{renderRow(index)}</div>
      </Fragment>
    })}
    {previous < offsets[keys.length] && <div aria-hidden="true" className="window-spacer" style={{ height: offsets[keys.length] - previous }} />}
  </div>
}

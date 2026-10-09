import { useState } from 'react'
import { Bookmark, ChevronDown, FileText, Search, SlidersHorizontal, Sparkles, Star, X } from 'lucide-react'
import type { CameraList, EventFilters } from '../lib/api'
import ArchiveFilters, { type FilterDraft } from './ArchiveFilters'
import DigestPanel from './DigestPanel'
import SavedViews from './SavedViews'
import SearchTools from './SearchTools'

const tools = [
  { id: 'filters', label: 'Filters', icon: SlidersHorizontal },
  { id: 'ai', label: 'AI search', icon: Sparkles },
  { id: 'views', label: 'Saved views', icon: Bookmark },
  { id: 'digest', label: 'Daily digest', icon: FileText },
] as const
const filterLabels = { query: 'Text', favourites: 'Favourites', camera_id: 'Camera', camera_ids: 'Cameras', category: 'Category', categories: 'Categories', color: 'Colour', direction: 'Direction', action: 'Action', source: 'Source', analysis: 'Analysis', start: 'From', end: 'Until', daypart: 'Time of day' } as const
type FilterKey = keyof typeof filterLabels

export default function ActivityTools({ query, favourites, draft, filters, cameras, timezone, onQuery, onFavourites, onDraft, onApply, onSavedView, onRemove, onClear, onClearFilters, onSearch, onRecording }: {
  query: string; favourites: boolean; draft: FilterDraft; filters: EventFilters; cameras: CameraList['items']; timezone: string
  onQuery: (value: string) => void; onFavourites: () => void; onDraft: (value: FilterDraft) => void
  onApply: (value: EventFilters) => void; onSavedView: (value: EventFilters, id: string) => void
  onRemove: (key: FilterKey) => void; onClear: () => void; onClearFilters: () => void; onSearch: () => void; onRecording: (id: string) => void
}) {
  const [open, setOpen] = useState<typeof tools[number]['id'] | null>(null)
  const active = (Object.keys(filterLabels) as FilterKey[]).filter(key => {
    const value = filters[key]
    return Array.isArray(value) ? value.length > 0 : !!value && !(key === 'daypart' && value === 'all')
  })
  const count = active.filter(key => key !== 'query' && key !== 'favourites').length
  function filterText(key: FilterKey): string {
    const value = filters[key]
    if (key === 'favourites') return 'Favourites only'
    if (key === 'start' || key === 'end') return `${filterLabels[key]}: ${new Date(String(value)).toLocaleString(undefined, { timeZone: timezone })}`
    const values = Array.isArray(value) ? value : [String(value)]
    const text = values.map(item => key === 'camera_id' || key === 'camera_ids' ? cameras.find(camera => camera.id === item)?.name ?? 'Selected camera' : item.replaceAll('_', ' ')).join(', ')
    return `${filterLabels[key]}: ${text}`
  }
  return <section className="activity-tools" aria-label="Activity search tools">
    <form className="filter-bar activity-search" onSubmit={event => { event.preventDefault(); onSearch() }}>
      <div className="search-field"><Search size={18} /><input aria-label="Search recordings" value={query} onChange={event => onQuery(event.target.value)} maxLength={200} placeholder="Search your notes and descriptions" /></div>
      <button type="button" className={favourites ? 'secondary selected' : 'secondary'} aria-pressed={favourites} onClick={onFavourites}><Star size={16} />Favourites</button>
    </form>
    <div className="activity-tool-buttons" role="group" aria-label="More search tools">
      {tools.map(tool => <button key={tool.id} id={`activity-${tool.id}-toggle`} type="button" className={open === tool.id ? 'secondary selected' : 'secondary'} aria-expanded={open === tool.id} aria-controls={`activity-${tool.id}-panel`} onClick={() => setOpen(previous => previous === tool.id ? null : tool.id)}>
        <tool.icon size={16} /><span>{tool.label}{tool.id === 'filters' && count > 0 ? ` · ${count}` : ''}</span><ChevronDown size={14} className={open === tool.id ? 'expanded-chevron' : undefined} />
      </button>)}
    </div>
    {active.length > 0 && <div className="active-filter-chips" aria-label="Active search filters">
      {active.map(key => <button key={key} className="filter-chip" onClick={() => onRemove(key)} aria-label={`Remove ${filterText(key)}`}><span>{filterText(key)}</span><X size={14} /></button>)}
      <button className="text-link" onClick={onClear}>Clear all</button>
    </div>}
    <div id="activity-filters-panel" role="region" aria-labelledby="activity-filters-toggle" hidden={open !== 'filters'}><ArchiveFilters value={draft} cameras={cameras} onChange={onDraft} onClear={onClearFilters} /></div>
    <div id="activity-ai-panel" role="region" aria-labelledby="activity-ai-toggle" hidden={open !== 'ai'}><SearchTools onApply={onApply} /></div>
    <div id="activity-views-panel" role="region" aria-labelledby="activity-views-toggle" hidden={open !== 'views'}><SavedViews filters={filters} onApply={onSavedView} /></div>
    <div id="activity-digest-panel" role="region" aria-labelledby="activity-digest-toggle" hidden={open !== 'digest'}><DigestPanel timezone={timezone} onRecording={onRecording} /></div>
  </section>
}

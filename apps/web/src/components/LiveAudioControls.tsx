import { Volume2, VolumeX } from 'lucide-react'
import { useId } from 'react'

export default function LiveAudioControls({ available, muted, volume, fullscreen = false, onToggle, onVolume }: {
  available: boolean; muted: boolean; volume: number; fullscreen?: boolean;
  onToggle: () => void; onVolume: (value: number) => void
}) {
  const id = useId()
  return <div className="live-audio-controls">
    <button className={fullscreen ? 'live-screen-button' : 'secondary'} disabled={!available} aria-label={muted ? 'Unmute audio' : 'Mute audio'} aria-pressed={!muted} onClick={onToggle}>
      {muted ? <VolumeX size={17} /> : <Volume2 size={17} />}{muted ? 'Unmute' : 'Mute'}
    </button>
    {available && <><label className="visually-hidden" htmlFor={id}>Live audio volume</label><input id={id} type="range" min="0" max="1" step="0.05" value={volume} onChange={event => onVolume(Number(event.target.value))} /></>}
  </div>
}

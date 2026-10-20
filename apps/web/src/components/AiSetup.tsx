import { useState } from 'react'
import { api, message, type AiReadiness, type Settings } from '../lib/api'

export default function AiSetup({ onSaved, onSkipped }: { onSaved: () => Promise<void>; onSkipped?: () => void }) {
  const [readiness, setReadiness] = useState<AiReadiness | null>(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState('')
  async function check() {
    setBusy(true); setFeedback('')
    try { setReadiness(await api<AiReadiness>('/setup/ai-readiness')) }
    catch (error) { setFeedback(message(error)) }
    finally { setBusy(false) }
  }
  async function skip() {
    setBusy(true); setFeedback('')
    try {
      const latest = await api<Settings>('/settings')
      if (latest.ai_enabled) await api('/settings', { method: 'PUT', body: JSON.stringify({ ...latest, ai_enabled: false }) })
      await api('/face-detection/control', { method: 'PUT', body: JSON.stringify({ enabled: false }) })
      await onSaved()
      setFeedback('Automatic descriptions and face scanning are off. Saved results and profiles are kept.')
      onSkipped?.()
    } catch (error) {
      setFeedback(`Check AI settings before continuing: ${message(error)}`)
      try { await onSaved() } catch { /* The original failure remains visible; do not advance. */ }
    }
    finally { setBusy(false) }
  }
  return <section className="panel settings-section beginner-setup">
    <h2>AI is optional</h2>
    <p>Start with your cameras and archive. Without AI, Porchlight still saves available Blink clips, plays video and audio, shows thumbnails, and supports notes, favourites and generic activity alerts.</p>
    <p className="helper">Camera names, recording times, duration and source come from Blink and the saved media. Person names, actions and smart filters require optional local analysis; Blink’s app descriptions are not assumed available through its unofficial API.</p>
    <div className="setup-choice-actions"><button className="primary" disabled={busy} onClick={() => { void skip() }}>Use Porchlight without AI</button><button className="secondary" disabled={busy} onClick={() => { void check() }}>{busy ? 'Checking…' : 'Check this PC for AI'}</button></div>
    {readiness && <div className="notice" role="status"><strong>{readiness.message}</strong><p>{readiness.ram_bytes === null ? 'RAM unknown' : `${(readiness.ram_bytes / 1024 ** 3).toFixed(1)} GiB RAM`} · {readiness.cpu_threads ?? 'Unknown'} CPU threads · {readiness.gpu_memory_bytes === null ? 'GPU memory not detected' : `${(readiness.gpu_memory_bytes / 1024 ** 3).toFixed(1)} GiB NVIDIA GPU memory`}</p><p className="helper">This is a conservative suggestion, not a compatibility benchmark. Other GPUs and CPU inference may work. Other apps compete for memory; the image test below is required before enabling descriptions.</p></div>}
    <details className="archive-help" open={!!readiness && readiness.recommendation !== 'skip'}><summary>Set up local AI</summary>
      <ol className="setup-instructions">
        <li><strong>Install Ollama on this PC.</strong> <a href="https://ollama.com/download/windows" target="_blank" rel="noreferrer">Download the official Windows installer</a>. Open Ollama afterward. Skip this if it is already installed.</li>
        <li><strong>Make Ollama local only.</strong> In PowerShell in the Porchlight folder, preview <code>.\scripts\setup-local-ai.ps1 -LocalOnly</code>, then repeat with <code>-Apply</code> if you agree. The helper preserves other settings and backs up changed configuration. Quit Ollama from its tray menu and reopen it. This disables cloud features for every app using that server. Keep its default loopback address.</li>
        <li><strong>Download a vision model.</strong> Allow extra disk space beyond the model download and Windows. Run this in PowerShell, after reviewing the model’s terms:
          <code className="guide-path">.\scripts\setup-local-ai.ps1 -Model {readiness?.suggested_model ?? 'qwen3-vl:4b'} -Apply</code>
          <a href={`https://ollama.com/library/${readiness?.suggested_model ?? 'qwen3-vl:4b'}`} target="_blank" rel="noreferrer">Model details and licence</a>. Nothing is downloaded by this page.</li>
        <li><strong>Check, test, then enable.</strong> Use Check local models below, select the downloaded model and run Test with a synthetic image. Choose {readiness?.suggested_workload === 'balanced' ? 'Balanced' : 'Light'} workload, tick automatic analysis and Save settings only after the test passes. Slow or failed? Leave AI off and revisit later.</li>
      </ol>
      <a className="text-link" href="/api/v1/setup/guides/local-ai">Download step-by-step AI instructions</a>
    </details>
    {feedback && <p role="status" className="feedback">{feedback}</p>}
  </section>
}

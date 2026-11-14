import { TONES, type Tone } from '../lib/types'

export function ToneSelector({ value, onChange, compact = false }: { value: Tone; onChange: (tone: Tone) => void; compact?: boolean }) {
  return <div className={`tone-options${compact ? ' compact' : ''}`} role="group" aria-label="Reply tone">
    {TONES.map(tone => <button key={tone.value} type="button" className={value === tone.value ? 'tone active' : 'tone'} aria-pressed={value === tone.value} onClick={() => onChange(tone.value)}>{tone.label}</button>)}
  </div>
}

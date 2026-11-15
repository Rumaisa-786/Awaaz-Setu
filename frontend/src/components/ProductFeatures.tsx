import { House, History, Settings } from 'lucide-react'

export type InputMode = 'type' | 'direct'
const modes: [InputMode, string][] = [['type', 'Type / Tap'], ['direct', 'Speak-Direct']]

export function InputModeSwitcher({ value, onChange }: { value: InputMode; onChange: (value: InputMode) => void }) {
  return <div className="mode-switch" role="group" aria-label="Reply input mode">{modes.map(([mode, label]) => <button key={mode} aria-pressed={value === mode} onClick={() => onChange(mode)}>{label}</button>)}</div>
}

export function SaveSummaryToggle({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return <label className="save-history-toggle"><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)}/><span>Save call summary &amp; transcript</span><small>Off by default. No audio is saved.</small></label>
}

export function MainNavigation({ onNavigate }: { onNavigate: (path: string) => void }) {
  return <nav className="bottom-nav" aria-label="Main navigation"><button onClick={() => onNavigate('/')}><House size={18}/>Home</button><button onClick={() => onNavigate('/history')}><History size={18}/>History</button><button onClick={() => onNavigate('/settings')}><Settings size={18}/>Settings</button></nav>
}

export function SummaryDialog({ summary, entities = [], saved, onClose }: { summary: { plain_language_summary: string; outcomes?: string[]; open_items?: string[] }; entities?: { type: string; value: string }[]; saved: boolean; onClose: () => void }) {
  return <div className="summary-overlay" role="dialog" aria-modal="true" aria-labelledby="summary-title"><section className="summary-card"><h2 id="summary-title">Call summary</h2><p>{summary.plain_language_summary}</p>{summary.outcomes?.length ? <><h3>Outcomes</h3><ul>{summary.outcomes.map((item, i) => <li key={i}>{item}</li>)}</ul></> : null}{summary.open_items?.length ? <><h3>Still to do</h3><ul>{summary.open_items.map((item, i) => <li key={i}>{item}</li>)}</ul></> : null}{entities.length > 0 && <><h3>Details mentioned</h3><ul>{entities.map((item, i) => <li key={`${item.type}-${i}`}>{item.value}</li>)}</ul></>}<div className="summary-actions"><button className="button secondary" onClick={() => void navigator.clipboard.writeText(summary.plain_language_summary)}>Copy summary</button><button className="button primary" onClick={onClose}>Done</button></div><p className="privacy-note">{saved ? 'Saved on this device.' : 'This summary and transcript were not saved.'}</p></section></div>
}

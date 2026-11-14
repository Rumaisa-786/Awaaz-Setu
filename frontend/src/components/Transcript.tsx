import { Languages } from 'lucide-react'
import type { TranscriptTurn } from '../lib/types'

export function Transcript({ turns, stableText, volatileText }: { turns: TranscriptTurn[]; stableText: string; volatileText: string }) {
  return <div className="transcript" aria-live="polite" aria-relevant="additions text">
    {turns.map((turn, index) => <article className={`bubble ${turn.role}`} key={`${turn.role}-${index}-${turn.text}`}>
      <div className="bubble-label">{turn.role === 'caller' ? 'Caller' : 'You'}{turn.language && <span><Languages size={13}/>{turn.language}</span>}</div>
      <p>{turn.text}</p>{turn.latency != null && <small>{turn.latency} ms STT</small>}
    </article>)}
    {(stableText || volatileText) && <article className="bubble caller partial"><div className="bubble-label">Caller · listening</div><p>{stableText}<span className="volatile">{volatileText}</span></p></article>}
  </div>
}

import { AlertTriangle, Check, Flag, Volume2 } from 'lucide-react'
import type { Entity } from '../lib/types'

export function EntityCards({ entities, risk, onReadBack, onDecision }: { entities: Entity[]; risk: boolean; onReadBack: (entity: Entity) => void; onDecision: (entity: Entity, action: 'confirm' | 'flag') => void }) {
  return <section className="entity-stack" aria-live="polite">
    {risk && <div className="risk-card" role="alert"><AlertTriangle aria-hidden="true"/><div><strong>Never share a code over a call</strong><p>Do not share an OTP, PIN, CVV, card number, or bank password.</p></div></div>}
    {entities.map((entity, index) => <article className="entity-card" key={`${entity.type}-${entity.value}-${index}`}>
      <div><span className="eyebrow">Please check this {entity.type.replace('_', ' ')}</span><strong className="entity-value">{entity.value}</strong></div>
      <div className="entity-actions">
        <button type="button" onClick={() => onReadBack(entity)}><Volume2 size={18}/>Read it back</button>
        <button type="button" onClick={() => onDecision(entity, 'confirm')}><Check size={18}/>Confirm</button>
        <button type="button" className="quiet" onClick={() => onDecision(entity, 'flag')}><Flag size={18}/>Flag</button>
      </div>
    </article>)}
  </section>
}

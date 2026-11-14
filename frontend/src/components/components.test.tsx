import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, createElement, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { EntityCards } from './EntityCards'
import { ToneSelector } from './ToneSelector'
import { Transcript } from './Transcript'

let host: HTMLDivElement
let root: Root
;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function render(node: ReactNode) {
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
  act(() => root.render(node))
}

afterEach(() => { if (root) act(() => root.unmount()); host?.remove() })

describe('call interface components', () => {
  it('renders entity confirmation values and the OTP safety warning', () => {
    render(createElement(EntityCards, { entities: [{ type: 'amount', value: '₹5,00,000' }], risk: true, onReadBack: vi.fn(), onDecision: vi.fn() }))
    expect(host.textContent).toContain('₹5,00,000')
    expect(host.textContent).toContain('Never share a code over a call')
    expect(host.querySelector('[role="alert"]')).not.toBeNull()
  })

  it('exposes tone selection as labelled pressed buttons', () => {
    const onChange = vi.fn()
    render(createElement(ToneSelector, { value: 'neutral', onChange }))
    const polite = Array.from(host.querySelectorAll('button')).find(button => button.textContent === 'Polite')!
    act(() => polite.click())
    expect(onChange).toHaveBeenCalledWith('polite')
    expect(host.querySelector('[aria-pressed="true"]')?.textContent).toBe('Neutral')
  })

  it('renders final captions, language, and a muted partial transcript', () => {
    render(createElement(Transcript, { turns: [{ role: 'caller', text: 'வணக்கம்', language: 'ta-IN', latency: 230 }], stableText: 'நாளை', volatileText: ' காலை' }))
    expect(host.textContent).toContain('வணக்கம்')
    expect(host.textContent).toContain('ta-IN')
    expect(host.textContent).toContain('230 ms STT')
    expect(host.querySelector('.volatile')?.textContent).toBe(' காலை')
  })
})

import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, createElement, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { EntityCards } from './EntityCards'
import { ToneSelector } from './ToneSelector'
import { Transcript } from './Transcript'
import { InputModeSwitcher, MainNavigation, SaveSummaryToggle, SummaryDialog } from './ProductFeatures'

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

  it('switches between Type / Tap and Speak-Direct', () => {
    const onChange = vi.fn(); render(createElement(InputModeSwitcher, { value: 'type', onChange }))
    expect(host.querySelectorAll('button')).toHaveLength(2)
    expect(host.textContent).not.toContain('Speak & Transform')
    expect(host.querySelectorAll('[aria-pressed="false"]')).toHaveLength(1)
    act(() => Array.from(host.querySelectorAll('button')).find(button => button.textContent === 'Speak-Direct')!.click())
    expect(onChange).toHaveBeenCalledWith('direct')
  })

  it('shows translated captions with their original language text', () => {
    render(createElement(Transcript, { turns: [{ role: 'caller', text: 'வணக்கம்', translated_text: 'नमस्ते', language: 'ta-IN' }], stableText: '', volatileText: '' }))
    expect(host.textContent).toContain('नमस्ते'); expect(host.textContent).toContain('Original: வணக்கம்')
  })

  it('keeps transcript saving opt-in and renders post-call summary', () => {
    const changed = vi.fn(); render(createElement('div', null, createElement(SaveSummaryToggle, { checked: false, onChange: changed }), createElement(SummaryDialog, { summary: { plain_language_summary: 'Appointment is tomorrow' }, saved: false, onClose: vi.fn() })))
    const toggle = host.querySelector('input[type="checkbox"]') as HTMLInputElement
    expect(toggle.checked).toBe(false); act(() => { toggle.click() }); expect(changed).toHaveBeenCalledWith(true)
    expect(host.querySelector('[role="dialog"]')?.textContent).toContain('Appointment is tomorrow')
  })

  it('provides product navigation for home, history and settings', () => {
    const navigate = vi.fn(); render(createElement(MainNavigation, { onNavigate: navigate }))
    expect(host.textContent).toContain('Home'); expect(host.textContent).toContain('History'); expect(host.textContent).toContain('Settings')
    act(() => Array.from(host.querySelectorAll('button')).find(button => button.textContent === 'History')!.click())
    expect(navigate).toHaveBeenCalledWith('/history')
  })
})

import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { AlertTriangle, ArrowLeft, Clipboard, Mic, MicOff, Phone, PhoneOff, Send, ShieldCheck, History, Settings } from 'lucide-react'
import { api, websocketUrl } from './lib/api'
import { EntityCards } from './components/EntityCards'
import { ToneSelector } from './components/ToneSelector'
import { Transcript } from './components/Transcript'
import { LANGUAGES, type CallConfig, type Entity, type Tone, type TranscriptTurn } from './lib/types'
import { supabase, supabaseConfigured } from './lib/supabase'
import { InputModeSwitcher, MainNavigation, SaveSummaryToggle, SummaryDialog, type InputMode } from './components/ProductFeatures'
type CreatedCall = { code: string; user_token: string }
type StoredCallConfig = CallConfig & { gate_demo?: boolean }
type RoomInfo = { code: string; state: string; goal: string; callee_connected: boolean }
type WSEvent = Record<string, any> & { type: string }
const defaultConfig: CallConfig = { goal: '', user_language: 'en-IN', callee_language: 'indic-auto', voice: 'female', tone: 'neutral', keyterms: [], use_keyterms: true }
function storedConfig(code: string): StoredCallConfig {
  try { const value = JSON.parse(sessionStorage.getItem(`awaaz-config:${code}`) || 'null'); return value ? { ...defaultConfig, ...value, voice: value.voice === 'male' || ['Avinash', 'Shubham', 'Prakash', 'Devansh', 'Yashraj', 'Harshad'].includes(value.voice) ? 'male' : 'female' } : defaultConfig } catch { return defaultConfig }
}
function routeFromPath() {
  const join = location.pathname.match(/^\/join\/([^/]+)/)
  const call = location.pathname.match(/^\/call\/([^/]+)/)
  if (join) return { page: 'join', code: join[1] }
  if (call) return { page: 'call', code: call[1] }
  return { page: location.pathname.replace(/^\//, '') || 'home', code: '' }
}
export default function App() {
  const [route, setRoute] = useState(routeFromPath)
  useEffect(() => { const update = () => setRoute(routeFromPath()); window.addEventListener('popstate', update); return () => window.removeEventListener('popstate', update) }, [])
  return route.page === 'join' ? <CalleeJoin code={route.code}/> : route.page === 'call' ? <UserCall code={route.code}/> : route.page === 'setup' ? <CallSetup/> : <ProductHome page={route.page}/>
}
function ProductHome({ page }: { page: string }) {
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [message, setMessage] = useState('')
  const [historyItems, setHistoryItems] = useState<any[]>(() => { try { return JSON.parse(localStorage.getItem('awaaz-history') || '[]') } catch { return [] } })
  useEffect(() => { if (page === 'history' && supabase) { void (async () => { const { data: { user } } = await supabase.auth.getUser(); if (!user) return; const { data } = await supabase.from('call_sessions').select('started_at,summary').eq('user_id', user.id).eq('saved', true).order('started_at', { ascending: false }).limit(100); if (data) setHistoryItems(data.map(item => ({ date: new Date(item.started_at).toLocaleString(), summary: item.summary }))) })() } }, [page])
  async function signIn() {
    if (!supabase) return
    const result = await supabase.auth.signInWithPassword({ email, password })
    if (result.error) { setMessage(result.error.message); return }
    if (result.data.session?.access_token) localStorage.setItem('awaaz-access-token', result.data.session.access_token)
    setMessage('Signed in successfully.')
  }
  async function signUp() {
    if (!supabase) return
    const result = await supabase.auth.signUp({ email, password })
    setMessage(result.error?.message || 'Check your email to finish creating your account.')
  }
  async function googleSignIn() {
    if (!supabase) return
    const result = await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: location.origin } })
    if (result.error) setMessage(result.error.message)
  }
  async function startGateDemo() {
    setMessage('Starting the scripted demo…')
    try {
      const config = { ...defaultConfig, user_language: 'en-IN', callee_language: 'hi-IN', goal: 'Scripted demo: simulated delivery at the main gate', gate_demo: true }
      const result = await api<CreatedCall>('/api/demo/gate', { method: 'POST', body: JSON.stringify({ user_language: config.user_language, voice: config.voice }) })
      sessionStorage.setItem(`awaaz-token:${result.code}`, result.user_token); sessionStorage.setItem(`awaaz-config:${result.code}`, JSON.stringify(config))
      history.pushState({}, '', `/call/${result.code}`); window.dispatchEvent(new PopStateEvent('popstate'))
    } catch (cause) { setMessage(cause instanceof Error ? cause.message : 'Could not start the demo.') }
  }
  function nav(path: string) { history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')) }
  return <main className="product-wrap"><Brand/><header className="home-intro"><span className="eyebrow">ACCESSIBLE CALLS</span><h1>{page === 'history' ? 'Call history' : page === 'settings' ? 'Accessibility & voice settings' : 'A clearer way to connect'}</h1><p>Voice relay in Indian languages, with your privacy in your hands.</p></header>
    {page === 'history' ? <section className="setup-card">{historyItems.length ? historyItems.map((item, index) => <article className="history-item" key={index}><strong>{item.date}</strong><p>{item.summary?.plain_language_summary}</p></article>) : <p>Saved calls appear here when you opt in to saving a summary.</p>}</section> : page === 'settings' ? <section className="setup-card"><label className="field-label">Caption text size<select className="input" onChange={event => document.documentElement.style.setProperty('--caption-size', `${event.target.value}px`)}><option value="18">Comfortable</option><option value="22">Large</option><option value="26">Extra large</option></select></label><p className="privacy-note">Calls are never recorded. Transcript and summary saving is off by default.</p></section> : <><section className="setup-card home-card"><button className="button primary full" onClick={() => nav('/setup')}><Phone size={18}/>New Call</button><div className="home-links"><button className="button secondary" onClick={() => nav('/history')}><History size={17}/>Call History</button><button className="button secondary" onClick={() => nav('/settings')}><Settings size={17}/>Accessibility &amp; Voice Settings</button></div><div className="auth-panel"><h2>{supabaseConfigured ? 'Sign in or create an account' : 'Continue as Guest (Local Demo Mode)'}</h2>{supabaseConfigured ? <><input className="input" type="email" aria-label="Email" value={email} onChange={event => setEmail(event.target.value)} placeholder="Email"/><input className="input" type="password" aria-label="Password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Password"/><button className="button secondary" onClick={signIn}>Sign in</button><button className="button secondary" onClick={signUp}>Create account</button><button className="button secondary" onClick={googleSignIn}>Continue with Google</button></> : <p>Your calls work without an account. History is stored on this device only, and only when you choose to save it.</p>}{message && <p role="status">{message}</p>}</div></section><section className="gate-launch-card"><span className="demo-badge">Scripted demo</span><h2>Gate Mode (Scripted Demo)</h2><p>Play a simulated delivery call at the main gate.</p><button className="button secondary" onClick={() => void startGateDemo()}>Start scripted delivery demo</button></section></>}
    <MainNavigation onNavigate={nav}/>
  </main>
}
function Brand({ back }: { back?: boolean }) {
  return <header className="brandbar"><div className="brand-mark" aria-hidden="true"><span/></div><div><strong>Awaaz Setu</strong><small>Voice bridge</small></div>{back && <a className="back-link" href="/"><ArrowLeft size={17}/>Setup</a>}</header>
}
function CallSetup() {
  const [config, setConfig] = useState<CallConfig>(defaultConfig)
  const [detailFields, setDetailFields] = useState(['Name', 'Date & Time', 'Location', 'Reference / Amount'])
  const [detailValues, setDetailValues] = useState<Record<string, string>>({})
  const [fieldsLoading, setFieldsLoading] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const detailPairs = Object.entries(detailValues).filter(([, value]) => value.trim())
  const contextTerms = useMemo(() => detailPairs.map(([, value]) => value.trim().slice(0, 80)).slice(0, 20), [detailValues])
  useEffect(() => {
    const goal = config.goal.trim()
    if (!goal) { setDetailFields(['Name', 'Date & Time', 'Location', 'Reference / Amount']); setFieldsLoading(false); return }
    let cancelled = false
    const timer = window.setTimeout(() => {
      setFieldsLoading(true)
      api<{ fields: string[] }>('/api/calls/context-fields', { method: 'POST', body: JSON.stringify({ goal }) })
        .then(result => { if (!cancelled && result.fields?.length) { setDetailFields(result.fields); setDetailValues(current => Object.fromEntries(result.fields.map(field => [field, current[field] || '']))) } })
        .catch(() => undefined).finally(() => { if (!cancelled) setFieldsLoading(false) })
    }, 500)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [config.goal])
  async function create(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true)
    try {
      const structuredGoal = (detailPairs.length ? `${config.goal.trim()}\nDetails: ${detailPairs.map(([label, value]) => `${label}: ${value}`).join('; ')}` : config.goal.trim()).slice(0, 500)
      const result = await api<CreatedCall>('/api/calls', { method: 'POST', body: JSON.stringify({ ...config, goal: structuredGoal, keyterms: contextTerms }) })
      sessionStorage.setItem(`awaaz-token:${result.code}`, result.user_token)
      sessionStorage.setItem(`awaaz-config:${result.code}`, JSON.stringify({ ...config, keyterms: contextTerms }))
      history.pushState({}, '', `/call/${result.code}`)
      window.dispatchEvent(new PopStateEvent('popstate'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not create a call.') }
    finally { setBusy(false) }
  }
  async function startGateDemo() {
    setError(''); setBusy(true)
    try {
      const demoConfig = { ...config, callee_language: 'hi-IN', goal: 'Scripted demo: simulated delivery at the main gate', gate_demo: true }
      const result = await api<CreatedCall>('/api/demo/gate', { method: 'POST', body: JSON.stringify({ user_language: config.user_language, voice: config.voice }) })
      sessionStorage.setItem(`awaaz-token:${result.code}`, result.user_token); sessionStorage.setItem(`awaaz-config:${result.code}`, JSON.stringify(demoConfig))
      history.pushState({}, '', `/call/${result.code}`); window.dispatchEvent(new PopStateEvent('popstate'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not start the scripted demo.') }
    finally { setBusy(false) }
  }
  return <main className="setup-wrap"><Brand/>
    <section className="setup-card">
      <div className="intro-copy"><span className="eyebrow">PRIVATE, LINK-BASED CALL</span><h1>Set up your call</h1><p>Choose how the reply should sound and add context that helps captions recognise names.</p></div>
      {error && <div className="inline-error" role="alert"><AlertTriangle size={18}/>{error}</div>}
      <form onSubmit={create}>
        <label className="field-label" htmlFor="goal">What is this call about?</label>
        <input id="goal" className="input" value={config.goal} onChange={event => setConfig({ ...config, goal: event.target.value })} placeholder="For example, book a clinic appointment" maxLength={500}/>
        <div className="setup-preferences">
          <label className="setup-language">User language<select className="input" value={config.user_language} onChange={event => setConfig({ ...config, user_language: event.target.value })}>{LANGUAGES.map(([code, name]) => <option key={code} value={code}>{name}</option>)}</select></label>
          <fieldset className="setup-voice"><legend>Voice</legend><div className="voice-segment"><button type="button" className={config.voice === 'female' ? 'selected' : ''} aria-pressed={config.voice === 'female'} onClick={() => setConfig({ ...config, voice: 'female' })}>Female</button><button type="button" className={config.voice === 'male' ? 'selected' : ''} aria-pressed={config.voice === 'male'} onClick={() => setConfig({ ...config, voice: 'male' })}>Male</button></div></fieldset>
        </div>
        <p className="auto-detect-note"><span className="status-dot online"/>Caller language is detected automatically</p>
        <div className="setup-tone"><strong>Default tone</strong><ToneSelector value={config.tone} onChange={tone => setConfig({ ...config, tone })}/></div>
        <section className="context-panel details-panel" aria-label="Details card">
          <div className="details-heading"><span><strong>DETAILS CARD</strong><small className="ai-label">AI Tailored</small></span><span className="fields-count">{detailFields.length} fields</span></div>
          <p className="details-caption">{fieldsLoading ? 'Finding useful details…' : 'Fields generated from your call purpose'}</p>
          <div className="context-body details-grid">{detailFields.map(field => <label key={field}>{field}<input className="input" value={detailValues[field] || ''} onChange={event => setDetailValues(current => ({ ...current, [field]: event.target.value }))} placeholder={field}/></label>)}</div>
          <label className="details-keyterms"><input type="checkbox" checked={config.use_keyterms} onChange={event => setConfig({ ...config, use_keyterms: event.target.checked })}/><span><strong>Use context keyterms</strong><small>Boost speech recognition accuracy with these details</small></span></label>
        </section>
        <button className="button primary full create-button" disabled={busy}>{busy ? 'Creating call…' : <><Phone size={18}/>Create call</>}</button>
      </form>
    </section>
      <p className="privacy-note"><ShieldCheck size={16}/>Assistive relay. Calls are not recorded by this prototype.</p>
  </main>
}
function UserCall({ code }: { code: string }) {
  const token = sessionStorage.getItem(`awaaz-token:${code}`) || ''
  const initial = storedConfig(code)
  const socket = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const [calleeConnected, setCalleeConnected] = useState(false)
  const [turns, setTurns] = useState<TranscriptTurn[]>([])
  const [stable, setStable] = useState('')
  const [volatile, setVolatile] = useState('')
  const [entities, setEntities] = useState<Entity[]>([])
  const [risk, setRisk] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [text, setText] = useState('')
  const [tone, setTone] = useState<Tone>(initial.tone)
  const [voice, setVoice] = useState(initial.voice)
  const [detectedLanguage, setDetectedLanguage] = useState('')
  const [useKeyterms, setUseKeyterms] = useState(initial.use_keyterms)
  const [keyterms] = useState<string[]>(initial.keyterms)
  const [status, setStatus] = useState('Connecting')
  const [error, setError] = useState('')
  const [preview, setPreview] = useState('')
  const [elapsed, setElapsed] = useState(0)
  const [linkCopied, setLinkCopied] = useState(false)
  const [mode, setMode] = useState<InputMode>('type')
  const [micOn, setMicOn] = useState(false)
  const [micLevel, setMicLevel] = useState(0)
  const [userPartial, setUserPartial] = useState('')
  const [saveAfterCall, setSaveAfterCall] = useState(false)
  const [summary, setSummary] = useState<any>(null)
  const [reconnecting, setReconnecting] = useState(false)
  const [demoTitle, setDemoTitle] = useState('')
  const [demoDisclosure, setDemoDisclosure] = useState('')
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false)
  const [sttLatency, setSttLatency] = useState<number | null>(null)
  const [ttsFirstByte, setTtsFirstByte] = useState<number | null>(null)
  const [llmStatus, setLlmStatus] = useState('Ready')
  const micStream = useRef<MediaStream|null>(null)
  const micContext = useRef<AudioContext|null>(null)
  const micProcessor = useRef<AudioWorkletNode|null>(null)
  const userAudioContext = useRef<AudioContext|null>(null)
  const userAudioChunks = useRef<Uint8Array[]>([])
  const ttsStartedAt = useRef<number|null>(null)
  const ending = useRef(false)
  const gateDemo = Boolean(initial.gate_demo)
  const detected = detectedLanguage || turns.slice().reverse().find(turn => turn.role === 'caller' && turn.language)?.language || ''
  useEffect(() => {
    let stopped = false
    let retryTimer = 0
    let attempt = 0
    let finalEnd = false
    function playGateAudio() {
      const chunks = userAudioChunks.current; userAudioChunks.current = []
      if (!chunks.length) return
      const size = chunks.reduce((total, item) => total + item.length, 0); const bytes = new Uint8Array(size)
      let offset = 0; chunks.forEach(item => { bytes.set(item, offset); offset += item.length })
      const context = userAudioContext.current || (userAudioContext.current = new AudioContext())
      void context.resume().then(() => context.decodeAudioData(bytes.buffer.slice(0))).then(buffer => { const source = context.createBufferSource(); source.buffer = buffer; source.connect(context.destination); source.start() }).catch(() => undefined)
    }
    const connect = () => {
      if (stopped || finalEnd) return
      setStatus(attempt ? 'Reconnecting…' : 'Connecting'); setReconnecting(attempt > 0)
      const ws = new WebSocket(websocketUrl(`/ws/call/user/${code}`)); socket.current = ws
      ws.onopen = () => { attempt = 0; setReconnecting(false); ws.send(JSON.stringify({ type: 'auth', token })) }
      ws.onmessage = event => {
        let data: WSEvent
        try { data = JSON.parse(event.data) as WSEvent } catch { return }
        switch (data.type) {
          case 'connected': setConnected(true); setCalleeConnected(Boolean(data.gate_demo)); setStatus(data.mock_mode ? 'Mock mode' : 'Connected'); break
          case 'transcript_history': setTurns((data.turns || []).map((turn: any) => ({ role: turn.role === 'caller' ? 'caller' : 'user', text: turn.text, translated_text: turn.translated_text, language: turn.language, voice: turn.voice }))); break
          case 'callee_status': setCalleeConnected(data.state === 'connected'); break
          case 'demo_banner': setDemoTitle(data.title); break
          case 'demo_disclosure': setDemoDisclosure(data.text); break
          case 'audio_chunk': if (data.audio) userAudioChunks.current.push(Uint8Array.from(atob(data.audio), (ch: string) => ch.charCodeAt(0))); break
          case 'tts_complete': playGateAudio(); break
          case 'partial_transcript': setStable(data.stable_text || ''); setVolatile(data.volatile_text || ''); setStatus('Caller is speaking'); break
          case 'speech_start': setStatus('Caller is speaking'); break
          case 'speech_end': setStatus('Your turn'); break
          case 'final_transcript':
            if (data.latency != null) setSttLatency(data.latency)
            if (data.detected_language_code) setDetectedLanguage(current => current || data.detected_language_code)
            setTurns(current => [...current, { role: 'caller', text: data.text, translated_text: data.translated_text, language: data.detected_language_code, latency: data.latency }]); setStable(''); setVolatile(''); setStatus('Your turn'); break
          case 'caption_translation': setTurns(current => current.map((turn, index) => index === data.turn_index ? { ...turn, translated_text: data.text } : turn)); break
          case 'entities': case 'entity_confirmation':
            setEntities(current => { const incoming = (data.entities || data.confirmed_entities || []).map((entity: any) => typeof entity === 'string' ? { type: 'detail', value: entity } : entity); const all = new Map(current.concat(incoming).map(entity => [`${entity.type}:${entity.value}`, entity])); return [...all.values()] }); setRisk(current => current || Boolean(data.otp_pin_cvv_request)); break
          case 'suggestions': setSuggestions(data.replies || []); break
          case 'tts_status':
            if (data.state === 'synthesizing') ttsStartedAt.current = performance.now()
            if (data.state === 'speaking' && ttsStartedAt.current != null) { setTtsFirstByte(Math.round(performance.now() - ttsStartedAt.current)); ttsStartedAt.current = null }
            setStatus(data.state === 'synthesizing' ? 'Synthesizing' : data.state === 'speaking' ? 'Speaking' : data.state === 'delivered' ? 'Delivered' : 'Ready'); break
          case 'connection_status': setStatus(data.state === 'connected' ? 'Connected' : 'Reconnecting…'); break
          case 'service_status': if (data.service === 'llm') setLlmStatus(data.state); break
          case 'error': setError(data.message); break
          case 'tone_preview': setPreview(data.text || ''); break
          case 'user_partial': setUserPartial(data.text || ''); break
          case 'user_final': setUserPartial(''); break
          case 'transform_spoken': setTurns(current => [...current, { role: 'user', text: data.text, translated_text: data.spoken_text, language: data.language, voice: data.voice }]); break
          case 'user_reply': setTurns(current => [...current, { role: 'user', text: data.text, translated_text: data.spoken_text, language: data.language, voice: data.voice }]); break
          case 'call_ended': finalEnd = true; ending.current = true; setStatus('Call ended'); setReconnecting(false); ws.close(); break
        }
      }
      ws.onclose = event => {
        setConnected(false)
        if ([4403, 4404].includes(event.code)) { finalEnd = true; setReconnecting(false); setStatus(event.code === 4403 ? 'Call access expired' : 'Call ended or expired'); return }
        if (!stopped && !finalEnd && !ending.current) {
          attempt += 1; const delay = Math.min(15000, 500 * (2 ** Math.min(attempt - 1, 5)))
          setReconnecting(true); setStatus('Reconnecting…'); retryTimer = window.setTimeout(connect, delay)
        } else if (!finalEnd) setStatus('Disconnected')
      }
    }
    connect()
    return () => { stopped = true; clearTimeout(retryTimer); socket.current?.close(); void userAudioContext.current?.close(); userAudioContext.current = null }
  }, [code, token])
  useEffect(() => { return () => { micProcessor.current?.disconnect(); micStream.current?.getTracks().forEach(track => track.stop()); void micContext.current?.close() } }, [])
  useEffect(() => { const timer = window.setInterval(() => setElapsed(value => value + 1), 1000); return () => clearInterval(timer) }, [])
  useEffect(() => { if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify({ type: 'context_settings', use_keyterms: useKeyterms, keyterms })) }, [useKeyterms, keyterms])
  useEffect(() => { if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify({ type: 'tone_settings', tone, voice })) }, [tone, voice])
  useEffect(() => { if (connected && socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify({ type: 'input_mode', mode })) }, [connected, mode])
  function sendReply(value: string) {
    const clean = value.trim(); if (!clean || socket.current?.readyState !== WebSocket.OPEN) return
    setError(''); setPreview(''); socket.current.send(JSON.stringify({ type: 'send_text', text: clean, tone, voice, language: initial.user_language })); setText('')
  }
  async function endCall() {
    ending.current = true
    try {
      const result = await api<any>(`/api/calls/${code}/end`, { method: 'POST', body: JSON.stringify({ user_token: token, save_history: saveAfterCall }) })
      setSummary(result.summary)
      if (saveAfterCall) {
        const saved = JSON.parse(localStorage.getItem('awaaz-history') || '[]'); saved.unshift({ date: new Date().toLocaleString(), summary: result.summary, turns }); localStorage.setItem('awaaz-history', JSON.stringify(saved.slice(0, 100)))
        if (supabase) {
          const { data: { user } } = await supabase.auth.getUser()
          if (user) {
            const inserted = await supabase.from('call_sessions').insert({ user_id: user.id, ended_at: new Date().toISOString(), language_pair: { user: initial.user_language, caller: detected }, summary: result.summary, saved: true }).select('id').single()
            if (!inserted.error && inserted.data) await supabase.from('opt_in_transcripts').insert({ call_session_id: inserted.data.id, user_id: user.id, turns })
          }
        }
      }
    } catch { socket.current?.send(JSON.stringify({ type: 'end_call' })) }
    stopMic(); setStatus('Call ended')
  }
  async function setInputMode(next: InputMode) {
    if (mode === next) return
    setMode(next)
    if (next === 'type') { stopMic(); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      const context = new AudioContext({ sampleRate: 16000 }); await context.audioWorklet.addModule('/src/pcm-worklet.js')
      const source = context.createMediaStreamSource(stream); const worklet = new AudioWorkletNode(context, 'pcm16-processor', { numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1 }); const mute = context.createGain(); mute.gain.value = 0
      source.connect(worklet); worklet.connect(mute); mute.connect(context.destination)
      worklet.port.onmessage = event => { if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(event.data); const bytes = new Int16Array(event.data); let sum = 0; bytes.forEach(n => { sum += n*n }); setMicLevel(Math.min(1, Math.sqrt(sum / bytes.length) / 14000)) }
      micStream.current = stream; micContext.current = context; micProcessor.current = worklet; setMicOn(true)
    } catch { setError('Microphone access is needed for this speaking mode.'); setMode('type'); socket.current?.send(JSON.stringify({ type: 'input_mode', mode: 'type' })) }
  }
  function stopMic() { micProcessor.current?.disconnect(); micProcessor.current = null; micStream.current?.getTracks().forEach(track => track.stop()); micStream.current = null; void micContext.current?.close(); micContext.current = null; setMicOn(false); setMicLevel(0); setUserPartial('') }
  function toggleMute() { const next = !micOn; setMicOn(next); micStream.current?.getAudioTracks().forEach(track => track.enabled = next) }
  async function previewTone() {
    if (socket.current?.readyState === WebSocket.OPEN && text.trim()) { socket.current.send(JSON.stringify({ type: 'preview_tone', text, tone })); setPreview('Tone preview requested…') }
  }
  function readBack(entity: Entity) { sendReply(`Just to confirm: ${entity.value}`) }
  async function copyJoinLink() { await navigator.clipboard.writeText(`${location.origin}/join/${code}`); setLinkCopied(true); window.setTimeout(() => setLinkCopied(false), 1800) }
  return <main className="call-page"><Brand back/>{demoTitle && <section className="demo-call-banner"><span className="demo-badge">Scripted Demo</span><strong>{demoTitle}</strong><p>Ramesh — Blinkit / Courier at Main Gate</p></section>}{reconnecting && <div className="reconnect-banner" role="status" aria-live="polite">Reconnecting… Your captions and replies will resume when the connection returns.</div>}{elapsed >= 810 && elapsed < 900 && <div className="reconnect-banner" role="alert">This call is approaching the Prisma 15-minute stream limit. The audio stream will reconnect automatically.</div>}<header className="call-header">
    <div><span className={`status-dot ${connected ? 'online' : ''}`}/><span>{calleeConnected ? 'Caller joined' : status}</span><span className="timer">{Math.floor(elapsed / 60).toString().padStart(2, '0')}:{(elapsed % 60).toString().padStart(2, '0')}</span></div>
    <label className="compact-toggle"><span>Context keyterms</span><input aria-label="Use context keyterms" type="checkbox" checked={useKeyterms} onChange={event => setUseKeyterms(event.target.checked)}/></label>
    <div className="language-pill"><span>Caller: {detected ? `${LANGUAGES.find(item => item[0] === detected)?.[1] || detected} (${detected})` : 'Detecting...'} → You: {LANGUAGES.find(item => item[0] === initial.user_language)?.[1]} ({initial.user_language})</span></div>
    <div className="call-actions"><button className="button secondary copy-call" onClick={copyJoinLink}><Clipboard size={17}/>{linkCopied ? 'Copied' : 'Join link'}</button><button className="button danger" onClick={endCall}><PhoneOff size={17}/>End call</button></div>
  </header>
  {error && <div className="inline-error" role="alert"><AlertTriangle size={17}/>{error}</div>}
  {llmStatus === 'fallback' && <div className="reconnect-banner" role="status" aria-live="polite">AI replies are temporarily unavailable. Captions and direct typing remain available.</div>}
  {demoDisclosure && <div className="demo-disclosure" role="status" aria-live="polite">{demoDisclosure}</div>}
  <section className="conversation-card">
    <EntityCards entities={entities} risk={risk} onReadBack={readBack} onDecision={(entity, action) => setEntities(current => current.filter(item => item !== entity))}/>
    <Transcript turns={turns} stableText={stable} volatileText={volatile}/>
    {!calleeConnected && <div className="waiting-state"><span className="pulse-dot"/>Waiting for the other caller to join</div>}
  </section>
  <section className="composer-card">
    <InputModeSwitcher value={mode} onChange={value => void setInputMode(value)}/>
    {mode === 'direct' && <div className="mic-mode-panel"><div><strong>Speak in {LANGUAGES.find(item => item[0] === initial.user_language)?.[1]}; your reply is translated and spoken to the caller</strong><p>{userPartial || 'Your speech will be transcribed and translated automatically.'}</p><div className="mic-meter" aria-label="Microphone level"><span style={{ width: `${Math.round(micLevel * 100)}%` }}/></div></div><button className="button secondary" onClick={toggleMute}>{micOn ? <MicOff size={18}/> : <Mic size={18}/>} {micOn ? 'Mute' : 'Unmute'}</button></div>}
    {mode === 'type' && <>
    <div className="composer-top"><strong>Suggested replies</strong><span>{suggestions.length ? 'In your language' : 'Suggestions appear after the caller speaks'}</span></div>
    {suggestions.length > 0 && <div className="suggestions">{suggestions.slice(0, 3).map((reply, index) => <button key={`${reply}-${index}`} onClick={() => sendReply(reply)}>{reply}</button>)}</div>}
    <div className="composer-tone"><ToneSelector value={tone} onChange={setTone} compact/><label className="voice-select">Speaking voice<select value={voice} onChange={event => setVoice(event.target.value)}><option value="female">Female</option><option value="male">Male</option></select></label></div>
    <form className="reply-form" onSubmit={event => { event.preventDefault(); sendReply(text) }}><input aria-label="Type your reply" className="input" value={text} maxLength={1000} onChange={event => { setText(event.target.value); if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify({ type: 'typing' })) }} placeholder="Type a reply for the caller"/><button type="button" className="button secondary preview-button" onClick={previewTone} disabled={!text.trim()}>Preview tone</button><button className="button primary" disabled={!text.trim() || !connected}><Send size={17}/>Send</button></form>
    {preview && <p className="preview-text" aria-live="polite">{preview}</p>}
    <div className="composer-status"><span className={`status-dot ${connected ? 'online' : ''}`}/>{status}</div>
    </>}
  </section>
  <details className="diagnostics" open={diagnosticsOpen} onToggle={event => setDiagnosticsOpen(event.currentTarget.open)}><summary>System Metrics &amp; Diagnostics</summary><div className="diagnostics-grid"><span>STT final latency</span><strong>{sttLatency == null ? '—' : `${sttLatency} ms`}</strong><span>TTS first byte</span><strong>{ttsFirstByte == null ? '—' : `${ttsFirstByte} ms`}</strong><span>Audio channels</span><strong>Isolated · {gateDemo ? 'scripted bridge' : 'dual WebSocket'}</strong><span>LLM</span><strong>{llmStatus}</strong></div></details>
  <SaveSummaryToggle checked={saveAfterCall} onChange={setSaveAfterCall}/>
  <p className="privacy-note"><ShieldCheck size={16}/>Call audio is processed for captions and speech and is not stored.</p>
  {summary && <SummaryDialog summary={summary} entities={entities} saved={saveAfterCall} onClose={() => { setSummary(null); history.pushState({}, '', '/'); window.dispatchEvent(new PopStateEvent('popstate')) }}/>}
  </main>
}
function CalleeJoin({ code }: { code: string }) {
  const [room, setRoom] = useState<RoomInfo | null>(null)
  const [joined, setJoined] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [micEnabled, setMicEnabled] = useState(true)
  const [userStatus, setUserStatus] = useState('Waiting for the user to reply')
  const [error, setError] = useState('')
  const socket = useRef<WebSocket | null>(null)
  const audioContext = useRef<AudioContext | null>(null)
  const mediaStream = useRef<MediaStream | null>(null)
  const audioChunks = useRef<Uint8Array[]>([])
  const directPlaybackAt = useRef(0)
  const leaving = useRef(false)
  const reconnectTimer = useRef<number | null>(null)
  useEffect(() => { api<RoomInfo>(`/api/calls/${code}`).then(setRoom).catch(cause => setError(cause.message || 'This call link is no longer available.')) }, [code])
  useEffect(() => () => { leaving.current = true; if (reconnectTimer.current != null) clearTimeout(reconnectTimer.current); socket.current?.close(); mediaStream.current?.getTracks().forEach(track => track.stop()); void audioContext.current?.close() }, [])
  async function joinCall() {
    setError(''); setConnecting(true)
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access is not available in this browser.')
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, sampleRate: 16000, echoCancellation: true, noiseSuppression: true, autoGainControl: true } })
      mediaStream.current = stream
      const context = new AudioContext({ sampleRate: 16000 }); audioContext.current = context
      await context.audioWorklet.addModule('/src/pcm-worklet.js')
      leaving.current = false
      let joinedOnce = false; let attempt = 0
      const connectSocket = () => new Promise<void>((resolve, reject) => {
        const ws = new WebSocket(websocketUrl(`/ws/call/callee/${code}`)); socket.current = ws; ws.binaryType = 'arraybuffer'
        ws.onopen = () => { attempt = 0; setUserStatus('Connected'); resolve() }
        ws.onerror = () => { if (!joinedOnce) reject(new Error('Could not connect to the call.')) }
        ws.onmessage = event => {
          if (event.data instanceof ArrayBuffer) { playDirectFrame(event.data); return }
          if (typeof event.data !== 'string') return
          const data = JSON.parse(event.data) as WSEvent
          if (data.type === 'user_status') setUserStatus(data.state === 'typing' ? 'The user is typing a reply' : data.state === 'speaking' ? 'The user is speaking' : 'The user has replied')
          if (data.type === 'tts_status') setUserStatus(data.state === 'speaking' ? 'The user is speaking' : userStatus)
          if (data.type === 'audio_chunk' && data.audio) audioChunks.current.push(Uint8Array.from(atob(data.audio), character => character.charCodeAt(0)))
          if (data.type === 'tts_complete') void playAudioChunks()
          if (data.type === 'call_ended') { leaving.current = true; setJoined(false); setUserStatus('Call ended') }
          if (data.type === 'error') setError(data.message)
        }
        ws.onclose = event => {
          if (!leaving.current && joinedOnce) {
            if (event.code === 4404) { leaving.current = true; setError('This call has ended or the link has expired.'); setJoined(false); return }
            attempt += 1; const delay = Math.min(15000, 500 * (2 ** Math.min(attempt - 1, 5)))
            setUserStatus('Reconnecting…'); reconnectTimer.current = window.setTimeout(() => { void connectSocket() }, delay)
          } else if (!leaving.current) reject(new Error('Could not connect to the call.'))
        }
      })
      await connectSocket(); joinedOnce = true
      const source = context.createMediaStreamSource(stream)
      const processor = new AudioWorkletNode(context, 'pcm16-processor', { numberOfInputs: 1, numberOfOutputs: 1, channelCount: 1 })
      const silent = context.createGain(); silent.gain.value = 0
      source.connect(processor); processor.connect(silent); silent.connect(context.destination)
      processor.port.onmessage = event => { if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(event.data) }
      setJoined(true); setUserStatus('Connected'); setRoom(current => current ? { ...current, callee_connected: true, state: 'live' } : current)
    } catch (cause) {
      mediaStream.current?.getTracks().forEach(track => track.stop()); mediaStream.current = null
      setError(cause instanceof Error ? cause.message : 'Could not join the call.')
    } finally { setConnecting(false) }
  }
  async function playAudioChunks() {
    const chunks = audioChunks.current; audioChunks.current = []
    if (!chunks.length || !audioContext.current) return
    const size = chunks.reduce((sum, chunk) => sum + chunk.length, 0); const joinedBytes = new Uint8Array(size)
    let offset = 0; for (const chunk of chunks) { joinedBytes.set(chunk, offset); offset += chunk.length }
    try {
      const audio = await audioContext.current.decodeAudioData(joinedBytes.buffer.slice(0))
      const source = audioContext.current.createBufferSource(); source.buffer = audio; source.connect(audioContext.current.destination); source.onended = () => setUserStatus('Waiting for the user to reply'); source.start()
    } catch { setError('The received audio could not be played. Please ask the user to resend the reply.') }
  }
  function playDirectFrame(frame: ArrayBuffer) {
    const context = audioContext.current
    if (!context || frame.byteLength !== 1024) return
    const view = new DataView(frame); const buffer = context.createBuffer(1, 512, 16000); const samples = buffer.getChannelData(0)
    for (let i = 0; i < 512; i++) samples[i] = view.getInt16(i * 2, true) / 32768
    const source = context.createBufferSource(); source.buffer = buffer; source.connect(context.destination)
    const now = context.currentTime; directPlaybackAt.current = Math.max(now + .01, directPlaybackAt.current); source.start(directPlaybackAt.current); directPlaybackAt.current += buffer.duration
  }
  function toggleMic() {
    const next = !micEnabled; setMicEnabled(next); mediaStream.current?.getAudioTracks().forEach(track => { track.enabled = next })
  }
  function leave() { leaving.current = true; if (reconnectTimer.current != null) clearTimeout(reconnectTimer.current); socket.current?.send(JSON.stringify({ type: 'leave' })); socket.current?.close(); mediaStream.current?.getTracks().forEach(track => track.stop()); setJoined(false) }
  return <main className="callee-wrap"><Brand/>
    <section className="callee-card">
      <div className="callee-icon"><Phone size={25}/></div>
      <span className="eyebrow">A secure call link</span>
      <h1>{error && !room ? 'Call link unavailable' : joined ? 'You’re connected' : 'Join the call'}</h1>
      <p className="disclosure">This call uses an assistive relay. Your speech is transcribed so the other person can read it and respond by voice. This prototype does not record calls.</p>
      {error && <div className="inline-error" role="alert"><AlertTriangle size={18}/>{error}</div>}
      {room && room.state !== 'ended' ? <>
        <div className="join-status" role="status" aria-live="polite"><span className={`status-dot ${joined ? 'online' : ''}`}/>{joined ? userStatus : 'Your microphone stays off until you join.'}</div>
        {!joined ? <button className="button primary full join-button" onClick={joinCall} disabled={connecting}><Mic size={18}/>{connecting ? 'Connecting…' : 'Join call'}</button> : <div className="join-controls"><button className="button secondary" onClick={toggleMic}>{micEnabled ? <MicOff size={18}/> : <Mic size={18}/>} {micEnabled ? 'Mute microphone' : 'Unmute microphone'}</button><button className="button danger" onClick={leave}><PhoneOff size={18}/>Leave call</button></div>}
      </> : <p className="inline-error">This call has ended or the link has expired.</p>}
      <p className="privacy-note"><ShieldCheck size={16}/>Your microphone audio is not played back locally.</p>
    </section>
  </main>
}

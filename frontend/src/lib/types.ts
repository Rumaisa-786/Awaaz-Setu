export type Tone = 'neutral' | 'warm' | 'polite' | 'urgent' | 'apologetic'
export type TranscriptTurn = { role: 'caller' | 'user'; text: string; translated_text?: string; language?: string; latency?: number; voice?: string }
export type Entity = { type: string; value: string; start?: number; end?: number }
export type CallConfig = { goal: string; user_language: string; callee_language: string; voice: string; tone: Tone; keyterms: string[]; use_keyterms: boolean }

export const LANGUAGES = [
  ['bn-IN', 'Bengali'], ['en-IN', 'English'], ['gu-IN', 'Gujarati'], ['hi-IN', 'Hindi'], ['kn-IN', 'Kannada'],
  ['ml-IN', 'Malayalam'], ['mr-IN', 'Marathi'], ['pa-IN', 'Punjabi'], ['ta-IN', 'Tamil'], ['te-IN', 'Telugu'],
] as const

export const VOICES = ['female', 'male']
export const TONES: { value: Tone; label: string }[] = [
  { value: 'neutral', label: 'Neutral' }, { value: 'warm', label: 'Warm' }, { value: 'polite', label: 'Polite' },
  { value: 'urgent', label: 'Urgent' }, { value: 'apologetic', label: 'Apologetic' },
]

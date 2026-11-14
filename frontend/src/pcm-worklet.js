class Pcm16Processor extends AudioWorkletProcessor {
  constructor() { super(); this.phase = 0; this.samples = [] }
  process(inputs, outputs) {
    const input = inputs[0]?.[0]
    const output = outputs[0]?.[0]
    if (output) output.fill(0)
    if (!input) return true
    const stride = sampleRate / 16000
    for (let i = 0; i < input.length; i++) {
      this.phase += 1
      if (this.phase >= stride) {
        this.phase -= stride
        this.samples.push(Math.max(-1, Math.min(1, input[i])))
        if (this.samples.length === 512) {
          const frame = new ArrayBuffer(1024)
          const view = new DataView(frame)
          for (let j = 0; j < 512; j++) view.setInt16(j * 2, Math.round(this.samples[j] * 32767), true)
          this.port.postMessage(frame, [frame])
          this.samples = []
        }
      }
    }
    return true
  }
}
registerProcessor('pcm16-processor', Pcm16Processor)

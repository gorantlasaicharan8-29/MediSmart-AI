/**
 * Synthesizes a clean, pleasant notification chime using the browser Web Audio API.
 * Requires zero external audio assets, works offline, and handles browser autoplay policies safely.
 */
let audioCtx = null

function getAudioContext() {
  if (typeof window === 'undefined') return null
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext
    if (AudioContextClass) {
      audioCtx = new AudioContextClass()
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {})
  }
  return audioCtx
}

export function playChime(type = 'turn') {
  try {
    const ctx = getAudioContext()
    if (!ctx) return

    const now = ctx.currentTime

    if (type === 'turn') {
      // Pleasant rising two-tone chime (C5 -> E5)
      const osc1 = ctx.createOscillator()
      const osc2 = ctx.createOscillator()
      const gain1 = ctx.createGain()
      const gain2 = ctx.createGain()

      osc1.type = 'sine'
      osc1.frequency.setValueAtTime(523.25, now) // C5
      gain1.gain.setValueAtTime(0.15, now)
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35)

      osc2.type = 'sine'
      osc2.frequency.setValueAtTime(659.25, now + 0.15) // E5
      gain2.gain.setValueAtTime(0.18, now + 0.15)
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.6)

      osc1.connect(gain1)
      gain1.connect(ctx.destination)
      osc2.connect(gain2)
      gain2.connect(ctx.destination)

      osc1.start(now)
      osc1.stop(now + 0.35)
      osc2.start(now + 0.15)
      osc2.stop(now + 0.6)
    } else if (type === 'call') {
      // Prominent three-tone waiting room bell (E5 -> G5 -> C6)
      const notes = [659.25, 783.99, 1046.5]
      notes.forEach((freq, idx) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        const start = now + idx * 0.18

        osc.type = 'triangle'
        osc.frequency.setValueAtTime(freq, start)
        gain.gain.setValueAtTime(0.2, start)
        gain.gain.exponentialRampToValueAtTime(0.001, start + 0.5)

        osc.connect(gain)
        gain.connect(ctx.destination)

        osc.start(start)
        osc.stop(start + 0.5)
      })
    }
  } catch (err) {
    // Autoplay policy or unsupported audio environment — safely ignore
    console.debug('Audio cue skipped:', err)
  }
}

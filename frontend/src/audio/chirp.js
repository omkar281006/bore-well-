// Plays the sounding chirp: the real 60–250 Hz sweep pitched up 4× so laptop speakers can
// reproduce it, followed by echoes after the actual round-trip delay for the current depth.
let actx = null;

export function playChirp(tauSeconds, enabled) {
  if (!enabled) return;
  try {
    if (!actx) actx = new (window.AudioContext || window.webkitAudioContext)();
    const t = actx.currentTime + 0.02;
    const voice = (t0, gain) => {
      const o = actx.createOscillator();
      const g = actx.createGain();
      const f = actx.createBiquadFilter();
      f.type = 'lowpass';
      f.frequency.value = 2200;
      o.type = 'sine';
      o.frequency.setValueAtTime(240, t0);
      o.frequency.exponentialRampToValueAtTime(1000, t0 + 0.25);
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(gain, t0 + 0.03);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.3);
      o.connect(f);
      f.connect(g);
      g.connect(actx.destination);
      o.start(t0);
      o.stop(t0 + 0.32);
    };
    voice(t, 0.16);
    voice(t + tauSeconds, 0.07);
    voice(t + tauSeconds * 2, 0.025);
  } catch (e) {
    /* audio unavailable */
  }
}

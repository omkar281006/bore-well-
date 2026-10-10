// Simulated acoustic sounding: a 60–250 Hz log chirp goes down the sounding tube,
// reflects off joints, the casing step and the water surface, and comes back with
// tube loss and pump noise. Matched filtering (cross-correlation) plus a
// time-varying gain finds the water echo; parabolic interpolation refines it.
import { ACOUSTIC, soundSpeed } from './constants.js';

let chirpCache = null;

function chirp() {
  if (chirpCache) return chirpCache;
  const { sampleRate: fs, chirpSeconds: Tc, f0, f1 } = ACOUSTIC;
  const k = f1 / f0;
  const M = Math.round(Tc * fs);
  const ch = new Float32Array(M);
  for (let i = 0; i < M; i++) {
    const t = i / fs;
    const phase = ((2 * Math.PI * f0 * Tc) / Math.log(k)) * (Math.pow(k, t / Tc) - 1);
    ch[i] = Math.sin(phase) * (0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (M - 1))); // Hann window
  }
  chirpCache = ch;
  return ch;
}

const loss = (depth) => Math.pow(10, (-ACOUSTIC.wallLossDbPerM * 2 * depth) / 20);

/** Run one ping against the current simulator state. Returns the waveform, envelope and depth estimate. */
export function computePing(s) {
  const fs = ACOUSTIC.sampleRate;
  const ch = chirp();
  const M = ch.length;
  const c = soundSpeed(s.temp);
  const N = Math.round(((2 * ACOUSTIC.maxDepth) / c + ACOUSTIC.chirpSeconds + 0.05) * fs);
  const rx = new Float32Array(N);
  const add = (depth, amp) => {
    const lag = Math.round(((2 * depth) / c) * fs);
    for (let i = 0; i < M && lag + i < N; i++) rx[lag + i] += amp * ch[i];
  };

  add(0, 0.9); // direct path from speaker to mic
  for (let d = 3; d <= 18; d += 3) add(d, 0.012 * loss(d)); // tube couplings
  add(20, 0.02 * loss(20)); // casing step
  const fe = s.sc.falseEcho;
  const falseEchoOn = !!(fe && s.t / 24 >= fe.start);
  if (falseEchoOn) add(fe.d, 0.4 * loss(fe.d));
  add(s.dl, 0.5 * loss(s.dl)); // water surface
  for (let i = 0; i < N; i++) {
    rx[i] += s.gauss() * 0.003 + (s.pumpOn ? 0.05 * Math.sin((2 * Math.PI * 100 * i) / fs) + 0.03 * Math.sin((2 * Math.PI * 48 * i) / fs) : 0);
  }

  // Matched filter.
  const nL = N - M;
  const corr = new Float32Array(nL);
  for (let l = 0; l < nL; l++) {
    let a = 0;
    for (let i = 0; i < M; i++) a += rx[l + i] * ch[i];
    corr[l] = a;
  }
  // Envelope with time-varying gain that undoes tube loss. The gain is capped (46 dB) so
  // amplified noise at the far end of the record can never outrank a real echo.
  const env = new Float32Array(nL);
  const hw = 6;
  for (let l = 0; l < nL; l++) {
    let m = 0;
    for (let j = Math.max(0, l - hw); j <= Math.min(nL - 1, l + hw); j++) m = Math.max(m, Math.abs(corr[j]));
    const depth = ((l / fs) * c) / 2;
    env[l] = m * Math.min(200, 1 / loss(depth));
  }
  const minL = Math.round(((2 * 4) / c) * fs); // ignore the first 4 m (direct path ringing)
  let best = minL;
  let bv = 0;
  for (let l = minL; l < nL; l++) if (env[l] > bv) { bv = env[l]; best = l; }
  // The envelope is a windowed max, so its argmax can sit up to `hw` samples off the true peak.
  // Snap to the largest raw correlation sample nearby before interpolating.
  const centre = best;
  for (let j = Math.max(minL, centre - hw); j <= Math.min(nL - 1, centre + hw); j++) {
    if (Math.abs(corr[j]) > Math.abs(corr[best])) best = j;
  }
  let frac = 0;
  if (best > 0 && best < nL - 1) {
    const y0 = Math.abs(corr[best - 1]);
    const y1 = Math.abs(corr[best]);
    const y2 = Math.abs(corr[best + 1]);
    const den = y0 - 2 * y1 + y2;
    if (den !== 0) frac = (0.5 * (y0 - y2)) / den;
  }
  const tau = (best + frac) / fs;
  return { rx, env, fs, c, tau, est: (tau * c) / 2, N, nL, temp: s.temp, falseEchoOn, trueDepth: s.dl };
}

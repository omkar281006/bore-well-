// Drawdown physics: Cooper–Jacob style log drawdown with wellbore storage,
// superposition of past pump events, a well-loss (skin) term, and neighbour interference.
import { STORATIVITY, WELLBORE_TAU } from './constants.js';

/** Transmissivity (m²/day) seen at a given water table: fractures above the water table stop contributing. */
export function transmissivityAt(swl, sc) {
  let T = sc.matrixT;
  for (const f of sc.fr) T += f.T / (1 + Math.exp(-(f.d - swl) / 1.2));
  return T;
}

/** Drawdown shape at the pumped well, with wellbore storage damping. tau in days. */
function wellFn(tau, T, rw) {
  if (tau <= 0) return 0;
  return Math.log(1 + (2.25 * T * tau) / (rw * rw * STORATIVITY)) * (1 - Math.exp(-tau / WELLBORE_TAU));
}

/** Drawdown shape at distance r from a pumped well. */
function distFn(tau, T, r) {
  if (tau <= 0) return 0;
  return Math.log(1 + (2.25 * T * tau) / (r * r * STORATIVITY));
}

/** Drawdown in our own well from all recent pump events (superposition). */
export function ownDrawdown(s, T) {
  const rw = s.sc.rw || 0.075;
  const td = s.t / 24;
  let tot = 0;
  for (const e of s.events) {
    const A = e.Q / (4 * Math.PI * T);
    const on = e.on / 24;
    tot += A * wellFn(td - on, T, rw);
    if (e.off != null) tot -= A * wellFn(td - e.off / 24, T, rw);
    const B = (e.Q / (2 * Math.PI * T)) * e.skin; // well loss from clogging
    if (B > 0) {
      if (e.off == null) tot += B * (1 - Math.exp(-(td - on) / WELLBORE_TAU));
      else tot += B * (1 - Math.exp(-(e.off - e.on) / 24 / WELLBORE_TAU)) * Math.exp(-(td - e.off / 24) / WELLBORE_TAU);
    }
  }
  return tot;
}

export function neighbourRunning(s) {
  const n = s.sc.neigh;
  if (!n) return false;
  const h = s.t % 24;
  return n.times.some((x) => h >= x && h < x + n.run);
}

/** Drawdown in our well caused by a neighbour's pumping (Theis superposition at distance r). */
export function neighbourDrawdown(s, T) {
  const n = s.sc.neigh;
  if (!n) return 0;
  const A = n.Q / (4 * Math.PI * T);
  const d0 = Math.floor(s.t / 24);
  let tot = 0;
  for (let d = d0 - 1; d <= d0; d++) {
    for (const h of n.times) {
      const on = d * 24 + h;
      const off = on + n.run;
      if (s.t > on) {
        tot += A * distFn((s.t - on) / 24, T, n.r);
        if (s.t > off) tot -= A * distFn((s.t - off) / 24, T, n.r);
      }
    }
  }
  return tot;
}

// Owns the well the app shows and the single animation loop.
//
// Two sources, same shape:
//   demo: the in-browser simulator (src/sim), stepped every frame
//   live: the BoreWise API (GET /wells/{id}), polled every few seconds and adapted by src/live/adapter.js
//
// The well object is mutable for speed; React re-renders on a throttled `tick`, while the 3D scene
// and canvas charts subscribe to every frame with useFrame().
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import {
  advance, computePing, DEFAULT_BORE, DEFAULT_SCENARIO, loadWell, ration as rationSim,
  setAuto as setAutoSim, setProtect as setProtectSim,
} from '../sim/index.js';
import { playChirp } from '../audio/chirp.js';
import { getWell, HAS_API, WELL_ID } from '../api/client.js';
import { reconstructedPingInput, toSimShape } from '../live/adapter.js';

const SimContext = createContext(null);
const AUTO_PING_SECONDS = 4.5;
const UI_REFRESH_MS = 150;
const POLL_MS = 4000;

export const reduceMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

function initialMode() {
  if (!HAS_API) return 'demo';
  try {
    return localStorage.getItem('bw-mode') || 'live';
  } catch (e) {
    return 'live';
  }
}

export function SimProvider({ children }) {
  const simRef = useRef(null); // demo simulator
  const liveRef = useRef(null); // adapted API data
  const pingRef = useRef(null);
  const frameSubs = useRef(new Set());
  const eventSubs = useRef(new Set());
  const [scenarioIdx, setScenarioIdx] = useState(DEFAULT_SCENARIO);
  const [boreIdx, setBoreIdx] = useState(DEFAULT_BORE);
  const [playing, setPlaying] = useState(!reduceMotion);
  const [speed, setSpeed] = useState(24); // simulated hours per real second
  const [lang, setLang] = useState('en');
  const [soundOn, setSoundOn] = useState(false);
  const [mode, setModeState] = useState(initialMode);
  const [liveStatus, setLiveStatus] = useState({ state: 'idle', message: '' });
  const [, setTick] = useState(0);
  const settings = useRef({ playing, speed, soundOn, mode });
  settings.current = { playing, speed, soundOn, mode };

  const emit = useCallback((type, payload) => eventSubs.current.forEach((fn) => fn(type, payload)), []);

  // (Re)build the demo simulator whenever the scenario or bore type changes, keeping pump switches.
  if (!simRef.current || simRef.current.__key !== scenarioIdx + ':' + boreIdx) {
    const prev = simRef.current;
    const sim = loadWell(scenarioIdx, boreIdx);
    sim.__key = scenarioIdx + ':' + boreIdx;
    if (prev) { sim.auto = prev.auto; sim.protect = prev.protect; }
    simRef.current = sim;
    if (mode === 'demo') pingRef.current = sim.pumpOn ? null : computePing(sim);
  }

  const current = () => (settings.current.mode === 'live' && liveRef.current ? liveRef.current : simRef.current);

  useEffect(() => {
    emit('scenario', { scenarioIdx, boreIdx, mode });
  }, [scenarioIdx, boreIdx, mode, emit]);

  // ---- live polling
  useEffect(() => {
    if (mode !== 'live') return undefined;
    let stop = false;
    let timer = 0;
    let lastBore = null;
    const poll = async () => {
      try {
        const res = await getWell(WELL_ID, 60);
        if (stop) return;
        const shaped = toSimShape(res);
        const first = !liveRef.current;
        liveRef.current = shaped;
        if (!shaped.pumpOn) pingRef.current = computePing(reconstructedPingInput(shaped));
        setLiveStatus({ state: 'ok', message: `${shaped.wellId} · updated ${new Date().toLocaleTimeString()}` });
        if (first || lastBore !== shaped.sc) emit('scenario', { live: true });
        lastBore = shaped.sc;
      } catch (err) {
        if (stop) return;
        setLiveStatus({ state: 'error', message: err.status === 404 ? `No telemetry for ${WELL_ID} yet. Run the simulator fleet or connect a device.` : `Cannot reach the API: ${err.message}` });
      }
      if (!stop) timer = setTimeout(poll, POLL_MS);
    };
    setLiveStatus({ state: 'loading', message: 'Connecting to the BoreWise API…' });
    poll();
    return () => { stop = true; clearTimeout(timer); };
  }, [mode, emit]);

  const firePing = useCallback((manual) => {
    const w = current();
    if (w.pumpOn) return null;
    const p = computePing(w.live ? reconstructedPingInput(w) : w);
    pingRef.current = p;
    emit('ping', p);
    if (manual || settings.current.soundOn) playChirp(p.tau, settings.current.soundOn);
    return p;
  }, [emit]);

  // ---- one animation loop for everything
  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let carry = 0;
    let lastUi = 0;
    let lastPing = 0;
    const loop = (now) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const { playing: on, speed: sp, mode: m } = settings.current;
      const sim = simRef.current;
      if (m === 'demo' && on && !sim.done) carry = advance(sim, carry + sp * dt);
      const w = current();
      const t = now / 1000;
      // Pings are gated to pump-off; while pumping, the last ping stays on screen.
      if (!w.pumpOn && on && t - lastPing > AUTO_PING_SECONDS) { lastPing = t; firePing(false); }
      frameSubs.current.forEach((fn) => fn(t, dt, w));
      if (now - lastUi > UI_REFRESH_MS) { lastUi = now; setTick((n) => n + 1); }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [firePing]);

  const setMode = useCallback((m) => {
    if (m === 'live' && !HAS_API) return;
    try { localStorage.setItem('bw-mode', m); } catch (e) { /* storage blocked */ }
    if (m === 'demo') pingRef.current = simRef.current.pumpOn ? null : computePing(simRef.current);
    setModeState(m);
  }, []);

  const isLive = mode === 'live' && Boolean(liveRef.current);
  const value = useMemo(() => ({
    simRef, liveRef, pingRef, scenarioIdx, boreIdx, playing, speed, lang, soundOn, mode, liveStatus, hasApi: HAS_API,
    setScenario: setScenarioIdx,
    setBore: setBoreIdx,
    togglePlay: () => setPlaying((p) => !p),
    setSpeed,
    setLang,
    setMode,
    toggleSound: () => setSoundOn((s) => !s),
    pingNow: () => firePing(true),
    // Pump control needs relay hardware, so these only act on the demo simulator.
    ration: (pct) => !isLive && rationSim(simRef.current, pct),
    setAuto: (on) => !isLive && setAutoSim(simRef.current, on),
    setProtect: (on) => !isLive && setProtectSim(simRef.current, on),
    subscribeFrame: (fn) => { frameSubs.current.add(fn); return () => frameSubs.current.delete(fn); },
    subscribeEvents: (fn) => { eventSubs.current.add(fn); return () => eventSubs.current.delete(fn); },
  }), [scenarioIdx, boreIdx, playing, speed, lang, soundOn, mode, liveStatus, firePing, setMode, isLive]);

  return <SimContext.Provider value={value}>{children}</SimContext.Provider>;
}

/** Current well (demo simulator or live API data) plus controls. Re-renders ~7 times a second. */
export function useSim() {
  const ctx = useContext(SimContext);
  if (!ctx) throw new Error('useSim must be used inside <SimProvider>');
  const live = ctx.mode === 'live' && ctx.liveRef.current;
  return { ...ctx, isLive: Boolean(live), sim: live || ctx.simRef.current, ping: ctx.pingRef.current };
}

/** Run `fn(time, dt, well)` on every animation frame. */
export function useFrame(fn) {
  const { subscribeFrame } = useContext(SimContext);
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => subscribeFrame((...a) => ref.current(...a)), [subscribeFrame]);
}

/** Listen for 'scenario' and 'ping' events. */
export function useSimEvents(fn) {
  const { subscribeEvents } = useContext(SimContext);
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => subscribeEvents((...a) => ref.current(...a)), [subscribeEvents]);
}

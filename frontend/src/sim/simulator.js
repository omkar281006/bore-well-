// Virtual borewell. Steps a well through a season at 2-minute resolution:
// pump schedule, drawdown and refill, seasonal decline and monsoon recharge,
// acoustic readings (only while the pump is off), and per-cycle recovery fits.
// Pure JS with no DOM, so the same code can run in a Lambda or an ECS simulator fleet.
import { evaluate } from './diagnosis.js';
import { neighbourDrawdown, neighbourRunning, ownDrawdown, transmissivityAt } from './hydraulics.js';
import { generateRain } from './rain.js';
import { SEASON_DAYS } from './constants.js';
import { clamp, fmtDay, fmtHM, makeGauss, mulberry32 } from './util.js';

export const STEP_HOURS = 1 / 30; // 2 minutes

export function createSim(sc, seed = 4242) {
  const s = {
    sc,
    gauss: makeGauss(mulberry32(seed)),
    t: sc.startDay * 24, // simulation hours since 1 Oct
    swl: sc.swl0, // static water table (m below ground)
    dl: sc.swl0, // true level inside the well
    meas: sc.swl0, // last acoustic measurement
    skin: sc.skin0 || 0,
    Q: sc.Q,
    runScale: 1, // 1 = full schedule; rationing lowers it
    pumpOn: false,
    auto: true, // run on schedule
    protect: true, // dry-run cut-off
    events: [],
    curEv: null,
    cur: null,
    readings: [],
    lastRead: null,
    nextRead: 0,
    lastOff: null,
    cycles: [],
    lastCycle: null,
    daily: [],
    findings: [],
    forecast: null,
    log: [],
    dryRun: false,
    emergency: null,
    interf: [],
    win: null,
    rain: generateRain(sc.seed, sc.rainF),
    lastDay: Math.floor(sc.startDay),
    peakDay: 0,
    temp: 27,
    T: transmissivityAt(sc.swl0, sc),
    I: 0, // motor current (A)
    done: false,
    dayPre: null,
  };
  s.nextOn = nextStart(s, s.t);
  s.nextRead = s.t;
  return s;
}

function nextStart(s, t) {
  let best = Infinity;
  const d0 = Math.floor(t / 24);
  for (let d = d0; d <= d0 + 1; d++) {
    for (const h of s.sc.sched) {
      const x = d * 24 + h;
      if (x > t + 1e-6 && x < best) best = x;
    }
  }
  return best;
}

export function addLog(s, text) {
  s.log.unshift(fmtDay(s.t / 24) + ' ' + fmtHM(s.t) + '  ' + text);
  if (s.log.length > 30) s.log.pop();
}

export function startPump(s) {
  if (s.cur) finalizeCycle(s);
  const ev = { on: s.t, off: null, Q: s.Q, skin: s.skin, Isum: 0, Ih: 0 };
  s.events.push(ev);
  if (s.events.length > 4) s.events.shift();
  s.pumpOn = true;
  s.curEv = ev;
  s.cur = { tOn: s.t, off: null, pre: s.lastRead ? s.lastRead.d : s.dl, Q: s.sc.Q, pts: [], ev, dry: false };
  if (s.dayPre == null) s.dayPre = s.cur.pre;
}

export function stopPump(s, dry = false) {
  if (!s.pumpOn) return;
  s.pumpOn = false;
  s.curEv.off = s.t;
  s.cur.off = s.t;
  s.cur.Ttrue = s.T;
  s.lastOff = s.t;
  s.nextRead = s.t + 1 / 60;
  if (dry) {
    s.cur.dry = true;
    s.emergency = { t: s.t, kind: 'dry' };
    addLog(s, 'Water at intake. Pump cut off.');
  }
}

/** Fit the Theis recovery line (residual drawdown vs log10(t/t')) for the cycle that just ended. */
function finalizeCycle(s) {
  const c = s.cur;
  s.cur = null;
  if (!c || c.off == null || c.pts.length < 4) return;
  const sEnd = c.pts[0].d - c.pre; // drawdown at pump stop
  const xs = [];
  const ys = [];
  for (const p of c.pts) {
    if (p.t - c.off < 0.75) continue; // skip early points dominated by well storage and skin
    xs.push(Math.log10((p.t - c.tOn) / (p.t - c.off)));
    ys.push(p.d - c.pre);
  }
  let a = NaN;
  let b = NaN;
  if (xs.length >= 3) {
    const n = xs.length;
    const mx = xs.reduce((u, v) => u + v, 0) / n;
    const my = ys.reduce((u, v) => u + v, 0) / n;
    let sxx = 0;
    let sxy = 0;
    for (let i = 0; i < n; i++) { sxx += (xs[i] - mx) ** 2; sxy += (xs[i] - mx) * (ys[i] - my); }
    a = sxx > 0 ? sxy / sxx : NaN;
    b = my - a * mx;
  }
  const T = a > 0.02 ? (2.303 * c.Q) / (4 * Math.PI * a) : NaN; // Theis recovery transmissivity
  const ev = c.ev;
  const cyc = {
    tOn: c.tOn, tOff: c.off, day: Math.floor(c.tOn / 24), pre: c.pre, sEnd, T, Ttrue: c.Ttrue,
    SC: c.Q / Math.max(sEnd, 0.05), // specific capacity, m³/day per m
    I: ev.Ih > 0 ? ev.Isum / ev.Ih : 0, pts: c.pts, a, b, dry: c.dry, run: c.off - c.tOn,
  };
  s.cycles.push(cyc);
  s.lastCycle = cyc;
  if (s.cycles.length > 3) s.cycles[s.cycles.length - 4].pts = null;
  if (s.cycles.length > 500) s.cycles.shift();
}

function measuredDepth(s) {
  const fe = s.sc.falseEcho;
  let d = s.dl;
  if (fe && s.t / 24 >= fe.start && s.dl > fe.d) d = fe.d;
  return d + s.gauss() * 0.025;
}

function takeReading(s) {
  const v = measuredDepth(s);
  const r = { t: s.t, d: v };
  s.readings.push(r);
  s.lastRead = r;
  s.meas = v;
  const since = s.lastOff != null ? s.t - s.lastOff : 99;
  s.nextRead = s.t + (since < 1 ? 2 / 60 : 0.25); // every 2 min while refilling, else every 15 min
  if (s.cur && s.cur.off != null) s.cur.pts.push(r);
  // Interference: the level falls while our pump has been off for > 2.5 h.
  if (since >= 2.5 && s.lastOff != null) {
    if (!s.win || s.win.off !== s.lastOff) s.win = { off: s.lastOff, min: v, hit: false };
    else {
      s.win.min = Math.min(s.win.min, v);
      if (!s.win.hit && v - s.win.min > 0.45) { s.win.hit = true; s.interf.push(s.t); }
    }
  }
}

export function step(s, dt = STEP_HOURS) {
  if (s.done) return;
  const sc = s.sc;
  s.t += dt;
  const day = Math.floor(s.t / 24);
  if (day !== s.lastDay) dayRollover(s, day);
  if (s.done) return;

  if (!s.pumpOn && s.t >= s.nextOn) {
    s.nextOn = nextStart(s, s.t);
    if (s.auto) startPump(s);
  }
  if (s.pumpOn && s.t >= s.curEv.on + sc.run * s.runScale) stopPump(s, false);

  const dd = dt / 24;
  if (sc.skinRate && day >= sc.skinStart) s.skin += sc.skinRate * dd;
  if (sc.wearRate && day >= sc.wearStart) s.Q *= 1 - sc.wearRate * dd;

  const T = transmissivityAt(s.swl, sc);
  s.T = T;
  const qn = neighbourRunning(s) ? sc.neigh.Q : 0;
  const rain = s.rain[Math.min(day, 365)] || 0;
  const recharge = clamp((s.swl - 5) / 15, 0.15, 1);
  s.swl += (0.03 + 0.0089 * (s.pumpOn ? s.Q : 0) + 0.0015 * qn) * dd - rain * 0.09 * recharge * dd;
  if (s.swl < 5) s.swl = 5;

  let own = ownDrawdown(s, T);
  if (sc.dug && s.swl < sc.dug.d) own *= 0.15; // the dug well's storage buffers drawdown
  let dl = s.swl + own + neighbourDrawdown(s, T);

  s.dryRun = false;
  if (s.pumpOn && dl >= sc.intake - 0.3) {
    s.dryRun = true;
    dl = Math.min(dl, sc.intake + 0.4);
    if (s.protect) stopPump(s, true);
    else if (!s.emergency || s.emergency.t < s.curEv.on) {
      s.emergency = { t: s.t, kind: 'dryon' };
      addLog(s, 'Pump running dry.');
    }
  }
  if (dl > sc.depth - 1) dl = sc.depth - 1;
  s.dl = dl;
  if (dl > s.peakDay) s.peakDay = dl;
  s.temp = 27.5 + 3.5 * Math.cos((2 * Math.PI * (s.t / 24 - 226)) / 365);
  s.I = s.pumpOn && sc.pumpKind !== 'hand' ? 5.6 * (0.68 + (0.32 * s.Q) / sc.Q) * (s.dryRun ? 0.62 : 1) : 0;
  if (s.pumpOn) { s.curEv.Isum += s.I * dt; s.curEv.Ih += dt; }
  if (!s.pumpOn && s.t >= s.nextRead) takeReading(s);
  if (s.readings.length > 2400) {
    const cut = s.t - 80;
    let i = 0;
    while (i < s.readings.length && s.readings[i].t < cut) i++;
    s.readings.splice(0, i);
  }
}

function dayRollover(s, day) {
  const prev = s.lastDay;
  s.daily.push({
    day: prev,
    swl: s.dayPre != null ? s.dayPre : s.lastRead ? s.lastRead.d : s.swl,
    swlTrue: s.swl,
    peak: s.peakDay,
    rain: s.rain[prev] || 0,
  });
  s.dayPre = null;
  s.peakDay = s.dl;
  s.lastDay = day;
  if (day >= SEASON_DAYS) s.done = true;
  evaluate(s);
}

/** Fast-forward to the scenario's starting moment. */
export function warmUp(s) {
  const w = s.sc.warm;
  if (!w) return;
  if (w.days != null) {
    const end = (s.sc.startDay + w.days) * 24;
    while (s.t < end && !s.done) step(s);
  } else {
    const end = (s.sc.startDay + w.max) * 24;
    while (!w.until(s) && s.t < end && !s.done) step(s);
  }
}

/** Advance the simulation by `hours`, capped so a slow frame cannot freeze the page. */
export function advance(s, hours, maxSteps = 9000) {
  let n = 0;
  let left = hours;
  while (left >= STEP_HOURS && n < maxSteps && !s.done) {
    step(s);
    left -= STEP_HOURS;
    n++;
  }
  return n >= maxSteps ? 0 : left; // carry the remainder to the next frame
}

/** Cut each run by `pct` percent. */
export function ration(s, pct) {
  s.runScale *= 1 - pct / 100;
  addLog(s, 'Rationing: runs cut ' + pct + '%.');
}

export function setAuto(s, on) {
  s.auto = on;
  if (!on && s.pumpOn) stopPump(s, false);
  addLog(s, on ? 'Schedule resumed.' : 'Pump held off.');
}

export function setProtect(s, on) {
  s.protect = on;
  addLog(s, 'Dry-run cut-off ' + (on ? 'on.' : 'off.'));
}

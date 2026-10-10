// Small numeric, random and date helpers shared by the simulator, diagnosis and UI.

/** Deterministic 32-bit PRNG so every scenario replays identically. */
export function mulberry32(seed) {
  let a = seed;
  return function next() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Box-Muller normal sampler bound to a PRNG. */
export function makeGauss(rand) {
  return () => {
    const u = rand() || 1e-9;
    const v = rand();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };
}

export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export function median(arr) {
  if (!arr.length) return NaN;
  const b = [...arr].sort((x, y) => x - y);
  const m = b.length >> 1;
  return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2;
}

/** Ordinary least squares on [x, y] pairs; returns slope, intercept and slope standard error. */
export function regress(pts) {
  const n = pts.length;
  if (n < 3) return null;
  let mx = 0;
  let my = 0;
  for (const p of pts) { mx += p[0]; my += p[1]; }
  mx /= n; my /= n;
  let sxx = 0;
  let sxy = 0;
  for (const p of pts) { sxx += (p[0] - mx) ** 2; sxy += (p[0] - mx) * (p[1] - my); }
  const m = sxy / sxx;
  const b = my - m * mx;
  let ss = 0;
  for (const p of pts) ss += (p[1] - (m * p[0] + b)) ** 2;
  const se = Math.sqrt(ss / Math.max(1, n - 2) / sxx);
  return { m, b, se };
}

// ---- Simulation calendar: hour 0 is 1 Oct 2026 (start of the dry season). ----
export const SEASON_START = new Date(2026, 9, 1, 0, 0, 0).getTime();
export const dateOf = (hours) => new Date(SEASON_START + hours * 3600e3);

export const MONTHS = {
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  mr: ['जानेवारी', 'फेब्रुवारी', 'मार्च', 'एप्रिल', 'मे', 'जून', 'जुलै', 'ऑगस्ट', 'सप्टेंबर', 'ऑक्टोबर', 'नोव्हेंबर', 'डिसेंबर'],
  hi: ['जनवरी', 'फ़रवरी', 'मार्च', 'अप्रैल', 'मई', 'जून', 'जुलाई', 'अगस्त', 'सितंबर', 'अक्टूबर', 'नवंबर', 'दिसंबर'],
};

/** "12 Mar" style date for a simulation day, in en / mr / hi. */
export function fmtDay(day, lang = 'en') {
  const dt = dateOf(day * 24);
  return dt.getDate() + ' ' + (MONTHS[lang] || MONTHS.en)[dt.getMonth()];
}

/** "06:45" for a simulation hour. */
export function fmtHM(hours) {
  const dt = dateOf(hours);
  return String(dt.getHours()).padStart(2, '0') + ':' + String(dt.getMinutes()).padStart(2, '0');
}

/** "1 h 30 min" for a duration in hours. */
export function fmtDur(hours) {
  const hh = Math.floor(hours);
  const mm = Math.round((hours - hh) * 60);
  return hh + ' h' + (mm ? ' ' + String(mm).padStart(2, '0') + ' min' : '');
}

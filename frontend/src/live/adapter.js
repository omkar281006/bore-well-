// Converts the API's GET /wells/{id} response into the same shape as the in-browser
// simulator, so every panel, chart and the 3D scene render live data unchanged.
// Hours and days are re-based onto the app's season calendar (hour 0 = 1 Oct 2026 local).
import { BORES } from '../sim/bores.js';
import { makeGauss, mulberry32, SEASON_START } from '../sim/util.js';

const BORE_BY_ID = Object.fromEntries(BORES.map((b) => [b.id, b]));
const gauss = makeGauss(mulberry32(7));
const scCache = new Map();

/** Static well config -> the `sc` object the scene and charts read. Cached so the 3D bore is not rebuilt every poll. */
function wellConfig(well) {
  const key = JSON.stringify([well.well_id, well.bore_type, well.depth_m, well.intake_m, well.pump_flow_m3_day, well.fractures]);
  if (scCache.has(key)) return scCache.get(key);
  const base = BORE_BY_ID[well.bore_type] || BORE_BY_ID.open;
  const bore = { ...base, depth: well.depth_m ?? base.depth, intake: well.intake_m ?? base.intake };
  const sc = {
    id: 'live',
    bore,
    depth: bore.depth,
    intake: bore.intake,
    Q: well.pump_flow_m3_day ?? base.Q,
    pumpKind: base.pump,
    rw: base.rw || 0.075,
    dug: base.dug || null,
    // Fractures come from the drilling log when the well was registered; unknown means none drawn.
    fr: (well.fractures || []).map((f) => ({ d: f.d, T: f.T ?? 6 })).filter((f) => f.d < bore.depth - 4),
    sched: [],
    run: 0,
    falseEcho: null,
  };
  scCache.set(key, sc);
  return sc;
}

export function toSimShape(res) {
  const offsetH = (new Date(res.season_start).getTime() - SEASON_START) / 3600e3;
  const H = (h) => h + offsetH;
  const D = (d) => (d == null ? d : d + offsetH / 24);
  const sc = wellConfig(res.well);
  const latest = res.latest || {};
  const fc = { ...(res.forecast || { state: 'learning' }) };
  for (const k of ['p10', 'p50', 'p90']) if (fc[k] != null) fc[k] = D(fc[k]);
  if (fc.rate == null) fc.rate = NaN;

  const readings = (res.readings || []).filter((r) => r.valid && r.d != null).map((r) => ({ t: H(r.h), d: r.d }));
  const cycles = (res.cycles || []).map((c) => ({
    tOn: H(c.t_on), tOff: H(c.t_off), day: D(c.day), pre: c.pre, sEnd: c.s_end, T: c.T ?? NaN, Ttrue: null,
    SC: c.SC, I: c.I, a: c.slope ?? NaN, b: c.intercept ?? NaN, run: c.run, dry: c.dry,
    pts: c.pts ? c.pts.map(([t, d]) => ({ t: H(t), d })) : null,
  }));
  const lastCycle = cycles.length ? cycles[cycles.length - 1] : null;
  const pumpOn = latest.pump_state === 'ON';
  const lastDepth = res.last_valid_depth_m ?? res.water_table_m ?? 0;
  const swl = res.water_table_m ?? lastDepth;
  const emergencyFinding = (res.findings || []).find((f) => f.msg === 'dry' || f.msg === 'dryon');
  const t = H(res.now_hours);

  // While pumping there is no measured depth; show the water table plus the typical drawdown.
  const dl = pumpOn ? swl + (fc.D || 0) : lastDepth;
  const findings = (res.findings || []).map((f) => (f.v && f.v.date != null ? { ...f, v: { ...f.v, date: D(f.v.date) } } : f));

  return {
    live: true,
    wellId: res.well.well_id,
    wellName: res.well.name,
    dataSource: latest.data_source,
    sc,
    t,
    swl,
    dl,
    meas: lastDepth,
    pumpOn,
    dryRun: emergencyFinding?.msg === 'dryon',
    emergency: emergencyFinding ? { t, kind: emergencyFinding.msg } : null,
    I: latest.pump_current_a ?? 0,
    temp: latest.temperature_c ?? 27,
    T: lastCycle && Number.isFinite(lastCycle.T) ? lastCycle.T : NaN,
    lastOff: lastCycle ? lastCycle.tOff : null,
    readings,
    cycles,
    lastCycle,
    cur: pumpOn && cycles.length ? { tOn: t - (latest.pump_run_minutes || 0) / 60, off: null } : null,
    daily: (res.daily || []).map((e) => ({ day: D(e.day), swl: e.swl, peak: e.peak, rain: res.rain_by_day ? res.rain_by_day[e.day] || 0 : 0 })),
    rain: res.rain_by_day ? shiftRain(res.rain_by_day, offsetH / 24) : new Array(366).fill(0),
    forecast: fc,
    findings,
    log: [],
    runScale: 1,
    auto: true,
    protect: true,
    done: false,
    echoTau: latest.echo_tau_ms ?? null,
    gauss,
    generatedAt: res.generated_at,
  };
}

function shiftRain(rain, dayOffset) {
  const off = Math.round(dayOffset);
  if (!off) return rain;
  const out = new Array(366).fill(0);
  rain.forEach((v, i) => { if (i + off >= 0 && i + off < 366) out[i + off] = v; });
  return out;
}

/** The echo the device would have recorded for the reported depth (for the echo chart). */
export function reconstructedPingInput(live) {
  return { ...live, pumpOn: false, dl: live.meas, sc: { ...live.sc, falseEcho: null } };
}

import { useRef, useState } from 'react';
import {
  ACOUSTIC, alertText, countAtRisk, FLEET, FLEET_STATUS_LABEL, fmtDay, fmtDur, fmtHM, LANGS, MONSOON_ONSET_DAY,
} from '../sim/index.js';
import { drawEcho, drawFleet, drawLast72, drawRecovery, drawSeason } from '../charts/draw.js';
import { useFrame, useSim } from '../hooks/SimProvider.jsx';
import { useToast } from '../hooks/useToast.jsx';
import { Card, CountUp, MagneticButton } from './Effects.jsx';

const FRAME_MS = 33;

/** Canvas redrawn at ~30 fps from the live simulator. */
function LiveCanvas({ draw, className = 'chart', onPositions, ...rest }) {
  const ref = useRef(null);
  const last = useRef(0);
  useFrame((time, dt, sim) => {
    if (!ref.current || time * 1000 - last.current < FRAME_MS) return;
    last.current = time * 1000;
    const out = draw(ref.current, sim);
    if (onPositions) onPositions(out);
  });
  return <canvas ref={ref} className={className} {...rest} />;
}

// ---------- KPI row ----------
export function KpiRow() {
  const { sim } = useSim();
  const fc = sim.forecast || { state: 'learning' };
  const day = sim.t / 24;
  const failing = fc.state === 'fail' || fc.state === 'dry';
  const dryWord = { ok: 'Safe', stable: 'Safe', monsoon: 'Rain', paused: '—', learning: '…' }[fc.state] || '—';
  const dryNote = failing ? 'days at current pumping' : { ok: 'lasts to the monsoon', stable: 'level holding', monsoon: 'monsoon recharge under way', paused: 'forecast paused', learning: 'learning the season' }[fc.state];
  const T = sim.lastCycle && Number.isFinite(sim.lastCycle.T) ? sim.lastCycle.T : sim.T;
  return (
    <section className="kpis" aria-label="Key numbers">
      <div className="kpi" style={{ '--i': 0 }}><span className="kpi-l">Depth to water</span><b><CountUp value={sim.meas} decimals={2} /></b><span className="kpi-u">metres below ground</span></div>
      <div className={'kpi' + (failing ? ' hot' : '')} style={{ '--i': 1 }}><span className="kpi-l">Dry in</span><b>{failing ? <CountUp value={Math.max(0, fc.p50 - day)} /> : dryWord}</b><span className="kpi-u">{dryNote}</span></div>
      <div className="kpi" style={{ '--i': 2 }}><span className="kpi-l">Transmissivity</span><b><CountUp value={T} decimals={1} /></b><span className="kpi-u">m²/day from the last refill</span></div>
      <div className="kpi" style={{ '--i': 3 }}><span className="kpi-l">Ward wells at risk</span><b><CountUp value={countAtRisk(day, sim)} /></b><span className="kpi-u">of {FLEET.length} dry before the monsoon</span></div>
    </section>
  );
}

// ---------- Forecast ----------
export function ForecastCard() {
  const { sim, ration, isLive } = useSim();
  const toast = useToast();
  const fc = sim.forecast || { state: 'learning' };
  const day = sim.t / 24;
  const pct = (d) => Math.max(0, Math.min(100, (d / 365) * 100)) + '%';
  const failing = fc.state === 'fail' || fc.state === 'dry';
  let big;
  let text;
  if (failing) {
    big = <>Dry around <em>{fmtDay(fc.p50)}</em></>;
    text = fc.state === 'dry'
      ? 'Peak drawdown already touches the intake. Shorten runs today.'
      : `Likely between ${fmtDay(fc.p10)} and ${fmtDay(Math.min(fc.p90, 364))}, before the monsoon reaches Pune. Cutting pumping ${fc.cut}% carries the well to 10 June.`;
  } else if (fc.state === 'ok') {
    big = <>Lasts to the <em>monsoon</em></>;
    text = `At ${fc.rate.toFixed(2)} m a day the well keeps about ${Math.max(0, fc.marginOnset).toFixed(0)} m of margin above the intake on 10 June.`;
  } else if (fc.state === 'stable') {
    big = <>Level is <em>holding</em></>;
    text = 'The water table is not falling. No dry-up expected this season.';
  } else if (fc.state === 'monsoon') {
    big = <>Monsoon <em>recharge</em></>;
    text = 'Rain is refilling the aquifer. The dry-season forecast restarts in October.';
  } else if (fc.state === 'paused') {
    big = <>Forecast <em>paused</em></>;
    text = 'The depth reading is not trustworthy. Check the sounding tube before relying on dates.';
  } else {
    big = <>Learning the <em>season</em></>;
    text = 'Collecting a few days of refill curves before forecasting.';
  }
  const apply = () => {
    ration(fc.cut);
    toast('Runs now ' + fmtDur(sim.sc.run * sim.runScale) + ' each');
  };
  return (
    <Card className="s-8" index={0}>
      <div className="card-head"><h2>Dry-up forecast</h2><span className="note">P10 to P90 range</span></div>
      <p className={'forecast-big' + (failing ? ' alarm' : '')}>{big}</p>
      <p className="forecast-p">{text}</p>
      <div className="tl">
        <div className="tl-track" />
        <div className="tl-mon" style={{ left: pct(MONSOON_ONSET_DAY), right: 0 }} />
        {failing && <div className="tl-band" style={{ left: pct(fc.p10), width: `calc(${pct(Math.min(fc.p90, 364))} - ${pct(fc.p10)})` }} />}
        {failing && <div className="tl-p50" style={{ left: pct(fc.p50) }} />}
        <div className="tl-now" style={{ left: pct(day) }} />
        <span className="tl-cap" style={{ left: pct(MONSOON_ONSET_DAY) }}>Monsoon ~10 Jun</span>
        <div className="tl-lbls"><span>Oct</span><span>Dec</span><span>Feb</span><span>Apr</span><span>Jun</span><span>Aug</span><span>Oct</span></div>
      </div>
      <dl className="kv">
        <div><dt>Falling</dt><dd>{Number.isFinite(fc.rate) ? fc.rate.toFixed(2) + ' m/d' : '—'}</dd></div>
        <div><dt>Peak drawdown</dt><dd>{fc.D ? fc.D.toFixed(1) + ' m' : '—'}</dd></div>
        <div><dt>Margin to intake</dt><dd>{fc.remaining != null ? Math.max(0, fc.remaining).toFixed(1) + ' m' : '—'}</dd></div>
      </dl>
      <div className="row">
        <MagneticButton className="btn primary" disabled={!fc.cut || isLive} onClick={apply}>{fc.cut ? `Cut pumping ${fc.cut}%` : 'Apply rationing'}</MagneticButton>
        {isLive && fc.cut ? <span className="muted small">Send this to the society as a new pumping schedule.</span> : null}
        {sim.runScale < 1 && <span className="muted small">Runs now {fmtDur(sim.sc.run * sim.runScale)} each.</span>}
      </div>
    </Card>
  );
}

// ---------- Diagnosis ----------
export function DiagnosisCard() {
  const { sim } = useSim();
  return (
    <Card className="s-4" index={1}>
      <div className="card-head"><h2>Diagnosis</h2><span className="note">updated daily</span></div>
      <ul className="finds">
        {sim.findings.map((f) => (
          <li key={f.title} className={'find sev-' + f.sev}>
            <i />
            <div><b>{f.title}</b><span>{f.detail}</span></div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

// ---------- Charts ----------
export function SeasonCard() {
  return (
    <Card className="s-8" index={2}>
      <div className="card-head"><h2>Season so far</h2><span className="note">water table, daily peak, rain, forecast</span></div>
      <LiveCanvas draw={drawSeason} className="chart tall" aria-label="Season chart of water table and forecast" />
      <div className="legend">
        <span style={{ color: 'var(--aqua)' }}>Water table (pre-pump)</span>
        <span style={{ color: 'var(--aqua-2)' }}>Daily deepest level</span>
        <span style={{ color: 'var(--laterite)' }}>Pump intake</span>
        <span style={{ color: 'var(--act)' }}>Forecast</span>
        <span style={{ color: '#6f9fc4' }}>Rain</span>
      </div>
    </Card>
  );
}

export function AlertCard() {
  const { sim, lang, setLang } = useSim();
  const top = sim.findings[0];
  return (
    <Card className="s-4" index={3}>
      <div className="card-head"><h2>Alert preview</h2><span className="note">WhatsApp</span></div>
      <div className="tabs" role="group" aria-label="Alert language">
        {LANGS.map((l) => (
          <button key={l.id} type="button" aria-pressed={lang === l.id} onClick={() => setLang(l.id)}>{l.label}</button>
        ))}
      </div>
      <div className="bubble" key={(top && top.title) + lang}>
        {alertText(top, lang)}
        <small>BoreWise · {fmtDay(sim.t / 24, lang)} {fmtHM(sim.t)}</small>
      </div>
      <p className="muted small">Written from the day's top finding. In production a Strands agent sends it through WhatsApp utility templates.</p>
    </Card>
  );
}

export function Last72Card() {
  return (
    <Card className="s-6" index={4}>
      <div className="card-head"><h2>Last 72 hours</h2><span className="note">measured depth · shaded = pump running</span></div>
      <LiveCanvas draw={drawLast72} aria-label="Depth over the last 72 hours" />
    </Card>
  );
}

export function RecoveryCard() {
  const { sim } = useSim();
  const c = sim.lastCycle;
  const stats = c ? [
    ['Run', fmtDur(c.run)], ['First drop', c.sEnd.toFixed(2) + ' m'], ['Slope', Number.isFinite(c.a) ? c.a.toFixed(2) + ' m/log' : '—'],
    ['T estimate', Number.isFinite(c.T) ? c.T.toFixed(1) + ' m²/d' : '—'],
    ...(c.Ttrue != null ? [['Simulator truth', c.Ttrue.toFixed(1) + ' m²/d']] : []),
    ['Specific capacity', c.SC.toFixed(1) + ' m³/d/m'],
  ] : [];
  return (
    <Card className="s-6" index={5}>
      <div className="card-head"><h2>Refill after the last run</h2><span className="note">Theis recovery fit</span></div>
      <LiveCanvas draw={drawRecovery} aria-label="Recovery curve with fitted line" />
      <div className="fit-stats">{stats.map(([k, v]) => <span key={k}>{k} <b>{v}</b></span>)}</div>
    </Card>
  );
}

export function EchoCard() {
  const { ping, pingRef, isLive } = useSim();
  return (
    <Card className="s-6" index={6}>
      <div className="card-head"><h2>Acoustic echo</h2><span className="note">{isLive ? 'reconstructed from the reported depth' : `${ACOUSTIC.f0}–${ACOUSTIC.f1} Hz log chirp`}</span></div>
      <LiveCanvas draw={(cv, s) => drawEcho(cv, pingRef.current, s.pumpOn)} aria-label="Received echo and matched-filter envelope" />
      {ping && (
        <div className="eq">
          <span>c = (331.3 + 0.606 × {ping.temp.toFixed(1)} °C) × (1 − {ACOUSTIC.tubeDispersion}) = <b>{ping.c.toFixed(1)} m/s</b></span>
          <span>τ = {(ping.tau * 1000).toFixed(1)} ms → depth = c·τ/2 = <b>{ping.est.toFixed(2)} m</b>{ping.falseEchoOn ? ` (true water ${ping.trueDepth.toFixed(1)} m)` : ''}</span>
          <span>Time-varying gain undoes {ACOUSTIC.wallLossDbPerM} dB/m tube loss. Joint echoes at 3–18 m and the casing step at 20 m stay small.</span>
        </div>
      )}
    </Card>
  );
}

export function FleetCard() {
  const { sim } = useSim();
  const posRef = useRef([]);
  const [tip, setTip] = useState(null);
  const n = countAtRisk(sim.t / 24, sim);
  const move = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    let best = null;
    let bd = 14;
    for (const p of posRef.current) {
      const d = Math.hypot(p.x - x, p.y - y);
      if (d < bd) { bd = d; best = p; }
    }
    setTip(best ? { p: best, x: Math.min(x + 14, r.width - 200), y: y + 12 } : null);
  };
  return (
    <Card className="s-6" index={7}>
      <div className="card-head"><h2>Ward groundwater radar</h2><span className="note">{n} of {FLEET.length} wells dry before the monsoon · map not to scale</span></div>
      <div className="fleet-wrap">
        <LiveCanvas draw={drawFleet} onPositions={(p) => (posRef.current = p)} className="chart tall" onMouseMove={move} onMouseLeave={() => setTip(null)} aria-label="Map of society borewells by ward" />
        {tip && (
          <div className="fleet-tip" style={{ left: tip.x, top: tip.y }}>
            <b>{tip.p.f.name}</b><br />
            <span className="muted">{tip.p.f.ward}</span><br />
            Water table {tip.p.st.swl.toFixed(1)} m<br />
            {FLEET_STATUS_LABEL[tip.p.st.st]}
            {tip.p.st.days != null && tip.p.st.days > 0 && tip.p.st.st !== 'ok' ? ` · ~${Math.round(tip.p.st.days)} days` : ''}
          </div>
        )}
      </div>
      <div className="legend">
        <span style={{ color: 'var(--ok)' }}>Lasts the season</span>
        <span style={{ color: 'var(--watch)' }}>Thin margin</span>
        <span style={{ color: 'var(--act)' }}>Dry before monsoon</span>
        <span style={{ color: 'var(--crit)' }}>Dry within 2 weeks</span>
      </div>
    </Card>
  );
}

// ---------- Explainer and parameters ----------
const STEPS = [
  ['1 · Chirp', 'Send a low sweep', 'A 60–250 Hz chirp travels down a 25 mm sounding tube. Low tones survive the 150 m round trip; kHz tones die in the tube.'],
  ['2 · Echo', 'Find the water', 'Cross-correlation picks the echo off the water surface. Depth is c·τ/2, corrected for air temperature and tube width.'],
  ['3 · Refill', 'Test the aquifer', 'When the pump stops, the refill curve is a free pump test. Its slope gives transmissivity; the first drop gives well efficiency.'],
  ['4 · Forecast', 'Name the day', 'Seasonal trend, peak drawdown and intake depth give a dry-up window and the rationing that carries you to the monsoon.'],
];

export function HowItWorks() {
  return (
    <Card className="s-8" index={8}>
      <div className="card-head"><h2>How BoreWise reads a borewell</h2></div>
      <ol className="steps">
        {STEPS.map(([n, t, p], k) => (
          <li key={n} style={{ '--k': k }}><span className="n">{n}</span><b>{t}</b><p>{p}</p></li>
        ))}
      </ol>
    </Card>
  );
}

export function ParamsCard() {
  const { sim } = useSim();
  const sc = sim.sc;
  const b = sc.bore;
  const rows = [
    ['Bore type', b.name], ['Bore depth', sc.depth + ' m'],
    ['Casing', b.screens ? 'PVC to bottom, slotted at fractures' : (b.casingKind === 'steel' ? 'Steel ' : 'PVC ') + (b.dug ? b.dug.d : 0) + '–' + b.casing + ' m, open hole below'],
    ['Pump', b.hp + ' at ' + sc.intake + ' m'], ['Pump output', Math.round(sc.Q / 1.44) + ' L/min'], ['Storativity', '3 × 10⁻⁴'],
    ['Water-bearing fractures', sc.fr.map((f) => f.d).join(', ') + ' m'], ['Sounding tube', '25 mm PVC'],
    ['Chirp', `${ACOUSTIC.f0}–${ACOUSTIC.f1} Hz, ${ACOUSTIC.chirpSeconds} s`], ['Tube correction', '−' + (ACOUSTIC.tubeDispersion * 100).toFixed(2) + ' % sound speed'],
  ];
  return (
    <Card className="s-4" index={9}>
      <div className="card-head"><h2>Well parameters</h2></div>
      <table className="params"><tbody>{rows.map(([k, v]) => <tr key={k}><td>{k}</td><td>{v}</td></tr>)}</tbody></table>
    </Card>
  );
}

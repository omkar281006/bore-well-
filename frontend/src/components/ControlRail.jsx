import { BORES, SCENARIOS, fmtDay, fmtDur, fmtHM, dateOf } from '../sim/index.js';
import { useSim } from '../hooks/SimProvider.jsx';
import { useToast } from '../hooks/useToast.jsx';
import { MagneticButton } from './Effects.jsx';

const SPEEDS = [[1, '1 h/s'], [6, '6 h/s'], [24, '1 d/s'], [168, '1 wk/s']];

export default function ControlRail() {
  const { sim, isLive, mode, liveStatus, scenarioIdx, boreIdx, playing, speed, soundOn, setScenario, setBore, togglePlay, setSpeed, toggleSound, pingNow, setAuto, setProtect } = useSim();
  const toast = useToast();
  const day = sim.t / 24;

  const ping = () => {
    const p = pingNow();
    toast(p ? 'Echo at ' + p.est.toFixed(2) + ' m' : 'Pump running. Pings wait for it to stop.');
  };

  return (
    <aside className="rail" aria-label="Simulation controls">
      <section>
        <p className="eyebrow">Season clock</p>
        <div className="clock">
          <span className="clock-date">{fmtDay(day)} {dateOf(sim.t).getFullYear()}</span>
          <span className="clock-time">{fmtHM(sim.t)} · day {Math.floor(day + 1)}</span>
        </div>
        <div className="season" aria-hidden="true">
          <i style={{ width: Math.min(100, (day / 365) * 100) + '%' }} />
          <em />
        </div>
        <div className="season-lbls"><span>1 Oct 2026</span><span>monsoon</span><span>30 Sep 2027</span></div>
        {mode === 'live' && (
          <p className={'live-status ' + liveStatus.state}>{liveStatus.message || 'Waiting for the API…'}</p>
        )}
        <div className="row">
          {!isLive && (
            <MagneticButton className="btn primary" onClick={togglePlay} disabled={sim.done}>
              {sim.done ? 'Season complete' : playing ? 'Pause' : 'Play'}
            </MagneticButton>
          )}
          <MagneticButton className="btn" onClick={ping}>Ping now</MagneticButton>
          <MagneticButton className={'btn' + (soundOn ? ' on' : '')} onClick={toggleSound} aria-pressed={soundOn}>
            {soundOn ? 'Sound on' : 'Sound off'}
          </MagneticButton>
        </div>
        {!isLive && (
          <div className="seg" role="group" aria-label="Simulation speed">
            {SPEEDS.map(([v, label]) => (
              <button key={v} type="button" aria-pressed={speed === v} onClick={() => setSpeed(v)}>{label}</button>
            ))}
          </div>
        )}
      </section>

      {isLive ? (
        <section>
          <p className="eyebrow">Live well</p>
          <table className="params"><tbody>
            <tr><td>Well</td><td>{sim.wellId}</td></tr>
            <tr><td>Data source</td><td>{sim.dataSource}</td></tr>
            <tr><td>Last echo τ</td><td>{sim.echoTau != null ? sim.echoTau.toFixed(1) + ' ms' : '—'}</td></tr>
            <tr><td>Motor current</td><td>{sim.I.toFixed(1)} A</td></tr>
            <tr><td>Pump cycles analysed</td><td>{sim.cycles.length}</td></tr>
          </tbody></table>
          <p className="muted small">Scenarios and bore types belong to the demo. In live mode the bore comes from the well's registration.</p>
        </section>
      ) : (<>
      <section>
        <p className="eyebrow">Scenario</p>
        <div className="scns">
          {SCENARIOS.map((s, i) => (
            <button key={s.id} type="button" className="scn" aria-pressed={i === scenarioIdx}
              onClick={() => { setScenario(i); toast(s.name + ' loaded'); }}>
              <b>{s.name}</b>
              <span>{s.blurb}</span>
            </button>
          ))}
        </div>
      </section>

      <section>
        <p className="eyebrow">Bore type</p>
        <div className="scns">
          {BORES.map((b, i) => (
            <button key={b.id} type="button" className="scn" aria-pressed={i === boreIdx}
              onClick={() => { setBore(i); toast(b.name + ' built'); }}>
              <b>{b.name}</b>
              <span>{b.blurb}</span>
              <span className="bore-meta">{b.depth} m · {b.hp}</span>
            </button>
          ))}
        </div>
      </section>
      </>)}

      <section>
        <p className="eyebrow">Pump</p>
        <label className="sw">
          <span>Run on schedule {!isLive && <span className="muted mono">{sim.sc.sched.length} × {fmtDur(sim.sc.run * sim.runScale)}</span>}</span>
          <input type="checkbox" id="autoSw" checked={sim.auto} disabled={isLive} onChange={(e) => setAuto(e.target.checked)} />
        </label>
        <label className="sw">
          <span>Dry-run cut-off</span>
          <input type="checkbox" id="protSw" checked={sim.protect} disabled={isLive} onChange={(e) => setProtect(e.target.checked)} />
        </label>
        {isLive && <p className="muted small">Pump switching from the app needs the relay board; the device's own dry-run cut-off stays active.</p>}
        <ul className="log">
          {sim.log.length ? sim.log.slice(0, 8).map((l, i) => <li key={i + l}>{l}</li>) : <li>No events yet.</li>}
        </ul>
      </section>
    </aside>
  );
}

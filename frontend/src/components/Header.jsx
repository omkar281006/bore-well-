import { useEffect, useState } from 'react';
import { countAtRisk, FLEET, SEVERITY_LABEL } from '../sim/index.js';
import { API_URL } from '../api/client.js';
import { useSim } from '../hooks/SimProvider.jsx';

function Logo() {
  return (
    <svg className="mark" viewBox="0 0 52 52" aria-hidden="true">
      <rect x="23" y="4" width="6" height="44" rx="3" fill="#1e3538" />
      <rect x="23" y="30" width="6" height="18" rx="3" fill="#80d9cd" />
      <circle className="r1" cx="26" cy="30" r="12" fill="none" stroke="#80d9cd" strokeWidth="1.6" />
      <circle className="r2" cx="26" cy="30" r="12" fill="none" stroke="#dcaa7e" strokeWidth="1.2" />
      <path d="M14 10a14 14 0 0 1 24 0" fill="none" stroke="#80d9cd" strokeWidth="2" strokeLinecap="round" opacity=".9" />
      <path d="M8 6a21 21 0 0 1 36 0" fill="none" stroke="#80d9cd" strokeWidth="2" strokeLinecap="round" opacity=".45" />
    </svg>
  );
}

export function Masthead({ isLight, onToggleTheme }) {
  const { sim, isLive, mode, setMode, hasApi, liveStatus } = useSim();
  const letters = 'BoreWise'.split('');
  return (
    <header className="mast">
      <div className="brand">
        <Logo />
        <div>
          <h1 className="ttl" aria-label="BoreWise">
            {letters.map((ch, i) => (
              <span key={i} className={i >= 4 ? 'w' : ''} style={{ '--d': i }} aria-hidden="true">{ch}</span>
            ))}
          </h1>
          <p className="tag"><b>Every pump cycle is an aquifer test.</b> Hear the water, read the refill, and know the day the borewell runs dry.</p>
        </div>
      </div>
      <div className="mast-meta">
        {hasApi && (
          <div className="mode-switch" role="group" aria-label="Data source">
            <button type="button" aria-pressed={mode === 'demo'} onClick={() => setMode('demo')}>Demo</button>
            <button type="button" aria-pressed={mode === 'live'} onClick={() => setMode('live')} title={API_URL}>Live API</button>
          </div>
        )}
        <span className={'chip live' + (mode === 'live' && liveStatus.state === 'error' ? ' err' : '')}>
          {mode === 'live' ? (isLive ? 'Live · ' + (sim.dataSource || 'telemetry') : liveStatus.state === 'error' ? 'API offline' : 'Connecting…') : 'Live simulation'}
        </span>
        <span className="chip"><b>{isLive ? sim.wellName || sim.wellId : 'Sahyadri Heights CHS'}</b>{isLive ? '' : ' · Baner, Pune'}</span>
        <span className="chip">{sim.sc.bore.name} · {sim.sc.depth} m</span>
        <button type="button" className="chip theme-btn" onClick={onToggleTheme} aria-label={isLight ? 'Switch to dark mode' : 'Switch to light mode'}>
          {isLight ? '☾ Dark' : '☀ Light'}
        </button>
      </div>
    </header>
  );
}

/** Scrolling telemetry strip. Rebuilt every 1.2 s so the marquee animation is not restarted every tick. */
export function Ticker() {
  const { sim, ping } = useSim();
  const [items, setItems] = useState([]);
  useEffect(() => {
    const build = () => {
      const day = sim.t / 24;
      const top = sim.findings[0] || { sev: 'ok' };
      setItems([
        ['● LIVE', null, true],
        ['Depth', sim.meas.toFixed(2) + ' m'],
        ['Water table', sim.swl.toFixed(1) + ' m'],
        ['Pump', sim.pumpOn ? 'ON ' + sim.I.toFixed(1) + ' A' : 'OFF'],
        ['Transmissivity', sim.T.toFixed(1) + ' m²/d'],
        ['Air in bore', sim.temp.toFixed(1) + ' °C'],
        ['Echo τ', ping ? (ping.tau * 1000).toFixed(0) + ' ms' : 'gated'],
        ['Rain today', (sim.rain[Math.floor(day)] || 0).toFixed(0) + ' mm'],
        ['Status', SEVERITY_LABEL[top.sev]],
        ['Ward', countAtRisk(day, sim) + '/' + FLEET.length + ' at risk'],
        ['Season day', Math.floor(day + 1) + ' / 365'],
      ]);
    };
    build();
    const id = setInterval(build, 1200);
    return () => clearInterval(id);
  }, [sim, ping]);
  const row = items.map(([k, v, live], i) => (
    <span key={i}>
      {live ? <b className="live">{k}</b> : <>{k} <b>{v}</b></>}
      <i>◆</i>
    </span>
  ));
  return (
    <div className="ticker" aria-label="Live telemetry">
      <div className="ticker-track">
        <div className="ticker-run">{row}</div>
        <div className="ticker-run" aria-hidden="true">{row}</div>
      </div>
    </div>
  );
}

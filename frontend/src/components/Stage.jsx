import { useEffect, useRef, useState } from 'react';
import { WellScene } from '../scene/WellScene.js';
import { CAMERA_LABELS, SCENARIO_CAMERA } from '../scene/layout.js';
import { SCENARIOS, SEVERITY_LABEL } from '../sim/index.js';
import { reduceMotion, useFrame, useSim, useSimEvents } from '../hooks/SimProvider.jsx';

const INTRO_DELAY_MS = reduceMotion ? 0 : 1500;

/** The 3D cutaway with the depth HUD and camera presets. */
export default function Stage({ isLight }) {
  const canvasRef = useRef(null);
  const labelsRef = useRef(null);
  const stageRef = useRef(null);
  const sceneRef = useRef(null);
  const introDone = useRef(false);
  const [failed, setFailed] = useState(false);
  const [cam, setCam] = useState('overview');
  const [flash, setFlash] = useState(0);
  const { sim, playing, speed } = useSim();
  const top = sim.findings[0] || { sev: 'ok' };

  useEffect(() => {
    let scene;
    try {
      scene = new WellScene(canvasRef.current, labelsRef.current, { reduceMotion });
    } catch (e) {
      console.error('3D view failed to start', e);
      setFailed(true);
      return undefined;
    }
    sceneRef.current = scene;
    const ro = new ResizeObserver(() => {
      const r = stageRef.current.getBoundingClientRect();
      scene.resize(r.width, r.height);
    });
    ro.observe(stageRef.current);
    const intro = setTimeout(() => {
      scene.goCam('overview', null, reduceMotion ? 0.01 : 3.6);
      introDone.current = true;
    }, INTRO_DELAY_MS);
    return () => {
      clearTimeout(intro);
      ro.disconnect();
      scene.dispose();
      sceneRef.current = null;
    };
  }, []);

  useEffect(() => {
    sceneRef.current?.setLight(isLight);
  }, [isLight]);

  useFrame((time, dt, s) => {
    sceneRef.current?.frame(time, dt, s, { playing, speed, severity: (s.findings[0] || {}).sev });
  });

  useSimEvents((type, payload) => {
    const scene = sceneRef.current;
    if (!scene) return;
    if (type === 'ping') scene.startPing(sim);
    if (type === 'scenario') {
      setFlash((n) => n + 1);
      scene.shock(0.03, true);
      if (introDone.current) {
        const target = payload.live || payload.mode === 'live' ? 'overview' : SCENARIO_CAMERA[SCENARIOS[payload.scenarioIdx].id] || 'overview';
        setCam(target);
        // Wait one frame so the new bore is built before flying to it.
        requestAnimationFrame(() => scene.goCam(target, sim));
      }
    }
  });

  const go = (name) => {
    setCam(name);
    if (sceneRef.current) {
      if (name !== 'overview') sceneRef.current.userTouched = true;
      sceneRef.current.goCam(name, sim);
    }
  };

  const crit = top.sev === 'crit';
  const refilling = sim.lastOff != null && sim.t - sim.lastOff < 1;
  return (
    <div className={'stage ring' + (crit ? ' crit' : '')} ref={stageRef}>
      <canvas className="gl" ref={canvasRef} aria-label="3D cutaway of the borewell and the basalt layers around it" />
      <div className="scan" aria-hidden="true" />
      {flash > 0 && <div className="flash" key={flash} aria-hidden="true" />}
      <div className="labels" ref={labelsRef} />
      {failed && <p className="no-gl">The 3D view needs WebGL, which this browser has turned off. The panels below still run.</p>}

      <div className="hud">
        <div className="hud-top">
          <span className="hud-label">Depth to water</span>
          <span className={'pill sev-' + top.sev}>{SEVERITY_LABEL[top.sev]}</span>
        </div>
        <div className="hud-depth">
          {sim.meas.toFixed(2)}
          <small>m</small>
        </div>
        <div className="hud-sub">
          <span>Water table <b>{sim.swl.toFixed(1)} m</b></span>
          <span>Pump <b>{sim.pumpOn ? (sim.dryRun ? 'DRY · ' : 'ON · ') + (sim.sc.pumpKind === 'hand' ? 'by hand' : sim.I.toFixed(1) + ' A') : 'off'}</b></span>
          <span>Air in bore <b>{sim.temp.toFixed(1)} °C</b></span>
          <span>Transmissivity <b>{Number.isFinite(sim.T) ? sim.T.toFixed(0) + ' m²/d' : '—'}</b></span>
        </div>
        <div className="hud-note">
          {sim.pumpOn
            ? 'Pumping. Readings paused until the pump stops; true level ' + sim.dl.toFixed(1) + ' m.'
            : refilling ? 'Refill in progress. Reading every 2 minutes.' : 'Pump off. Reading every 15 minutes.'}
        </div>
      </div>

      <div className="cams" role="group" aria-label="Camera views">
        {CAMERA_LABELS.map(([id, label]) => (
          <button key={id} type="button" aria-pressed={cam === id} onClick={() => go(id)}>{label}</button>
        ))}
      </div>
      <div className="hint">Drag to orbit · Scroll to zoom</div>
    </div>
  );
}

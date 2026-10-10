// Run with `npm test` (uses Node's built-in test runner, no extra packages).
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadWell, advance, computePing, SCENARIOS, step } from './index.js';

const idx = (id) => SCENARIOS.findIndex((s) => s.id === id);

test('over-pumping forecasts a dry-up before the monsoon', () => {
  const sim = loadWell(idx('overpump'), 0);
  assert.equal(sim.forecast.state, 'fail');
  assert.ok(sim.forecast.p50 < 252);
  assert.ok(sim.forecast.cut >= 5 && sim.forecast.cut <= 90);
});

test('recovery fit recovers transmissivity within 25%', () => {
  const sim = loadWell(idx('healthy'), 0);
  advance(sim, 48);
  const c = sim.lastCycle;
  assert.ok(Number.isFinite(c.T));
  assert.ok(Math.abs(c.T - c.Ttrue) / c.Ttrue < 0.25, `T=${c.T} true=${c.Ttrue}`);
});

test('acoustic ping finds the water within 0.5 m', () => {
  const sim = loadWell(idx('healthy'), 0);
  while (sim.pumpOn) step(sim);
  const p = computePing(sim);
  assert.ok(Math.abs(p.est - sim.dl) < 0.5, `est=${p.est} true=${sim.dl}`);
});

test('dry-run cut-off stops the pump', () => {
  const sim = loadWell(idx('dry'), 0);
  advance(sim, 72);
  assert.ok(sim.findings.some((f) => f.sev === 'crit'));
});

test('sensor fault pauses the forecast', () => {
  const sim = loadWell(idx('sensor'), 0);
  advance(sim, 24 * 10);
  assert.equal(sim.forecast.state, 'paused');
});

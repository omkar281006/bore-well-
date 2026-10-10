// Headless validation: runs every bore type through every failure scenario for 45 simulated days
// and reports which findings fire. Run with `npm run validate`.
import { BORES, SCENARIOS, loadWell, step, SEVERITY_LABEL } from '../src/sim/index.js';

const EXPECTED = {
  healthy: null, overpump: 'Dry before the monsoon', fracture: 'Fracture dewatered', interf: 'Level drops while your pump is off',
  clog: 'Well clogging', weak: 'Weak monsoon', wear: 'Pump delivering less water', dry: 'Pump cut off', sensor: 'Depth reading not responding',
};

let pass = 0;
let total = 0;
const rows = [];
for (let b = 0; b < BORES.length; b++) {
  for (let i = 0; i < SCENARIOS.length; i++) {
    const sim = loadWell(i, b);
    const seen = new Map();
    const end = Math.min(365, Math.floor(sim.t / 24) + 45) * 24;
    while (sim.t < end && !sim.done) {
      step(sim);
      for (const f of sim.findings) if (!seen.has(f.title)) seen.set(f.title, f.sev);
    }
    const id = SCENARIOS[i].id;
    const want = EXPECTED[id];
    const titles = [...seen.keys()];
    const hit = want ? titles.some((t) => t.startsWith(want)) : true;
    total++;
    if (hit) pass++;
    rows.push({
      bore: BORES[b].id, scenario: id, caught: want ? (hit ? 'yes' : 'NO') : '-',
      forecast: sim.forecast.state, findings: titles.map((t) => t + ' [' + SEVERITY_LABEL[seen.get(t)] + ']').join('; '),
    });
  }
}
console.table(rows);
console.log(`\nCaught ${pass} of ${total} scenario × bore combinations.`);

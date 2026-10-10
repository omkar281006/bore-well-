// A ward-level fleet of 36 simulated Pune society borewells for the groundwater radar map.
// The fleet uses a cheap linear decline model; our own well (self) uses the full simulator.
import { MONSOON_ONSET_DAY } from './constants.js';
import { mulberry32 } from './util.js';

export const WARDS = [
  { n: 'Hinjewadi', x: 0.08, y: 0.32 }, { n: 'Wakad', x: 0.2, y: 0.5 }, { n: 'Baner', x: 0.33, y: 0.3 },
  { n: 'Aundh', x: 0.45, y: 0.52 }, { n: 'Kharadi', x: 0.78, y: 0.36 }, { n: 'Wagholi', x: 0.92, y: 0.56 },
  { n: 'Ambegaon', x: 0.5, y: 0.82 }, { n: 'Undri', x: 0.7, y: 0.78 },
];

const SOCIETIES = ['Indrayani Residency', 'Pawana Park', 'Mula Vista', 'Sinhagad Towers', 'Godavari Greens', 'Krishna Kunj', 'Tamhini Terraces', 'Bhima Enclave', 'Neera Nest', 'Purandar Palms', 'Kaveri Court', 'Shivneri Springs', 'Rajgad Rise', 'Torna Trees', 'Panshet Pines', 'Varasgaon View', 'Khadakwasla Crest', 'Mulshi Meadows', 'Pashan Point', 'Sus Gardens', 'Balewadi Bay', 'Viman Vista', 'Hadapsar Haven', 'Bavdhan Brook', 'Kondhwa Corner', 'Lohgad Lane', 'Visapur Villas', 'Harihar Heights', 'Tikona Terrace', 'Raigad Residency', 'Pratapgad Park', 'Sahyadri Square', 'Chakan Chambers', 'Ghod Gardens', 'Nira Nagar'];

export const SELF_WELL = { name: 'Sahyadri Heights CHS', ward: 'Baner', x: 0.33, y: 0.3, self: true };

export const FLEET = (() => {
  const r = mulberry32(77);
  const out = [];
  let k = 0;
  WARDS.forEach((w, wi) => {
    const n = wi === 2 ? 4 : wi % 2 ? 5 : 4;
    for (let i = 0; i < n; i++) {
      const a = r() * Math.PI * 2;
      const rad = 0.03 + r() * 0.06;
      out.push({
        name: SOCIETIES[k++ % SOCIETIES.length] + ' CHS', ward: w.n,
        x: w.x + Math.cos(a) * rad, y: w.y + Math.sin(a) * rad * 1.3,
        swl0: 12 + r() * 20, dec: 0.07 + r() * 0.36, D: 5 + r() * 9, intake: 90 + r() * 18,
      });
    }
  });
  out.push(SELF_WELL);
  return out;
})();

export const FLEET_STATUS_LABEL = { ok: 'Lasts the season', watch: 'Thin margin', act: 'Dry before monsoon', crit: 'Dry within 2 weeks' };

/** Status of one fleet well on a given day. `sim` is used for our own well. */
export function fleetState(w, day, sim) {
  if (w.self) {
    const fc = sim.forecast || {};
    let st = 'ok';
    if (fc.state === 'fail') st = fc.p50 - day < 14 ? 'crit' : 'act';
    else if (fc.state === 'dry') st = 'crit';
    else if (fc.state === 'ok' && fc.marginOnset < 10) st = 'watch';
    return { st, swl: sim.swl, days: fc.p50 ? fc.p50 - day : null };
  }
  const ON = MONSOON_ONSET_DAY;
  let swl = w.swl0 + w.dec * Math.min(day, ON);
  if (day > ON) swl -= ((day - ON) / 112) * (w.dec * ON);
  const rem = w.intake - 2 - w.D - swl;
  if (day > ON) return { st: 'ok', swl };
  const dleft = rem / w.dec;
  let st = 'ok';
  if (rem <= 0 || dleft < 14) st = 'crit';
  else if (day + dleft < ON) st = 'act';
  else if (rem - w.dec * (ON - day) < 10) st = 'watch';
  return { st, swl, days: dleft };
}

export function countAtRisk(day, sim) {
  return FLEET.reduce((n, w) => {
    const st = fleetState(w, day, sim).st;
    return n + (st === 'act' || st === 'crit' ? 1 : 0);
  }, 0);
}

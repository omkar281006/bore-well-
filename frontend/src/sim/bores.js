// Bore construction types common around Pune. Each changes the 3D model and the physics
// (depth, pump size and intake, effective well radius, starting skin).

export const BORES = [
  {
    id: 'open', name: 'Open-hole borewell',
    blurb: '6½″ bore in basalt. Steel casing through the weathered zone, bare rock below.',
    depth: 120, intake: 103, Q: 172.8, pump: 'sub', hp: '1.5 HP submersible',
    r: 0.2, casing: 20, casingKind: 'steel', dryOff: 18,
  },
  {
    id: 'screen', name: 'Screened tubewell',
    blurb: '8″ PVC casing to the bottom, slotted at each fracture, gravel pack around it.',
    depth: 120, intake: 100, Q: 216, pump: 'sub', hp: '2 HP submersible',
    r: 0.24, casing: 120, casingKind: 'pvc', screens: true, rw: 0.12, skin0: -0.8, dryOff: 16,
  },
  {
    id: 'dug', name: 'Dug-cum-bore well',
    blurb: 'A 5 m stone-lined dug well with a borewell drilled from its floor. Common on farms.',
    depth: 110, intake: 95, Q: 259.2, pump: 'sub', hp: '3 HP submersible',
    r: 0.2, casing: 22, casingKind: 'steel', dug: { d: 14, R: 0.95 }, dryOff: 22,
  },
  {
    id: 'hand', name: 'Hand-pump borewell',
    blurb: 'India Mark II head on a 4½″ bore. A cylinder and rods lift water by hand.',
    depth: 80, intake: 46, Q: 24, pump: 'hand', hp: 'India Mark II',
    r: 0.16, casing: 15, casingKind: 'pvc', sched: [6, 7.5, 9, 11, 13, 16, 17.5, 19], run: 0.4, dryOff: 1.8,
  },
];

export const DEFAULT_BORE = 0;

/** Combine a failure scenario with a bore type into the config the simulator runs. */
export function applyBore(scenario, bore) {
  const sc = { ...scenario };
  sc.bore = bore;
  sc.depth = bore.depth;
  sc.intake = bore.intake;
  sc.Q = bore.Q;
  sc.pumpKind = bore.pump;
  sc.skin0 = bore.skin0 || 0;
  sc.dug = bore.dug || null;
  sc.rw = bore.rw || 0.075; // effective well radius (m)
  sc.fr = scenario.fr.filter((f) => f.d < bore.depth - 4);
  if (bore.sched) { sc.sched = bore.sched; sc.run = bore.run; }
  sc.swl0 = scenario.id === 'dry' ? bore.intake - bore.dryOff : Math.min(scenario.swl0, bore.intake - 20);
  return sc;
}

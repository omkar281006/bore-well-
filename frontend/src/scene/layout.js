// Scene scale and geology. 1 scene unit = 10 m of depth; the cutaway block is L units wide.

export const K = 0.1; // scene units per metre of depth
export const L = 7; // cutaway block size
export const WELL = { x: 0.6, z: 0.6 }; // well position inside the notch corner
export const PUMP_HOUSE = { x: -1.1, z: 1.3 };

/** Deccan Trap lava-flow sequence around Pune (depths in m). */
export const LAYERS = [
  { n: 'Topsoil', a: 0, b: 3, c: '#5f4b3c', v: 0 },
  { n: 'Weathered basalt', a: 3, b: 20, c: '#585548', v: 40 },
  { n: 'Vesicular basalt', a: 20, b: 45, c: '#3e4b4c', v: 230 },
  { n: 'Red bole', a: 45, b: 50, c: '#6b4438', v: 0 },
  { n: 'Massive basalt', a: 50, b: 90, c: '#2c3638', v: 12 },
  { n: 'Vesicular basalt', a: 90, b: 110, c: '#35434a', v: 230 },
  { n: 'Massive basalt', a: 110, b: 150, c: '#262f31', v: 12 },
];

/** Camera presets: [position, target]. Functions receive the live sim. */
export const CAMERAS = {
  overview: () => [[18, 4, 21], [0, -6.2, 0]],
  wellhead: () => [[3.4, 1.7, 4.4], [WELL.x, -0.3, WELL.z]],
  water: (sim) => {
    const y = -sim.dl * K;
    return [[5.8, y + 2.4, 7.6], [WELL.x + 0.8, y, WELL.z + 0.8]];
  },
  fractures: () => [[13.5, -4.5, 12.5], [2.4, -6.5, 2.4]],
  pump: (sim) => {
    const y = -sim.sc.intake * K;
    return [[3.1, y + 1.3, 3.9], [WELL.x, y, WELL.z]];
  },
};

export const CAMERA_LABELS = [
  ['overview', 'Overview'],
  ['wellhead', 'Wellhead'],
  ['water', 'Water table'],
  ['fractures', 'Fractures'],
  ['pump', 'Pump'],
];

/** Which camera to fly to when a scenario loads. */
export const SCENARIO_CAMERA = { fracture: 'fractures', dry: 'pump', interf: 'water', clog: 'water', sensor: 'wellhead', weak: 'water', wear: 'pump' };

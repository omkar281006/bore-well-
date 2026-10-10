// Failure scenarios. Each one starts from BASE and overrides what makes it fail.
// `warm` fast-forwards the season to the interesting moment before the demo starts.

/** Water-bearing fractures in a typical Pune deep-basalt bore: depth (m) and transmissivity (m²/day). */
export const NORMAL_FRACTURES = [
  { d: 22, T: 8 },
  { d: 48, T: 5 },
  { d: 76, T: 10 },
  { d: 98, T: 9 },
];

export const BASE_SCENARIO = {
  Q: 172.8, // m³/day while running (120 L/min)
  matrixT: 2, // m²/day from the rock matrix
  fr: NORMAL_FRACTURES,
  swl0: 18, // starting water table (m below ground)
  startDay: 0,
  sched: [6, 18], // pump start hours
  run: 1, // run length (h)
  depth: 120,
  intake: 103,
  rainF: 1,
  seed: 11,
};

export const SCENARIOS = [
  { id: 'healthy', name: 'Healthy season', blurb: 'Two 1-hour runs a day. Should last to the monsoon.', warm: { days: 60 } },
  { id: 'overpump', name: 'Over-pumping', blurb: 'Three 2-hour runs a day for a 120-flat society.', sched: [6, 13, 20], run: 2, warm: { days: 100 } },
  {
    id: 'fracture', name: 'Fracture dewatering', blurb: 'Most water enters through one fracture at 48 m.',
    fr: [{ d: 22, T: 4 }, { d: 48, T: 22 }, { d: 76, T: 4 }, { d: 98, T: 4 }], run: 1.5,
    warm: { until: (s) => s.swl >= 43.5, max: 230 },
  },
  { id: 'interf', name: 'Neighbour interference', blurb: 'A borewell 30 m away pumps at 09:30 and 21:30.', neigh: { Q: 400, r: 30, times: [9.5, 21.5], run: 2 }, warm: { days: 40 } },
  { id: 'clog', name: 'Well clogging', blurb: 'Encrustation builds up in the open hole from November.', skinRate: 0.1, skinStart: 31, warm: { days: 46 } },
  { id: 'weak', name: 'Weak monsoon', blurb: 'June to September rain at 45% of normal.', rainF: 0.45, run: 1.5, warm: { days: 244 } },
  { id: 'wear', name: 'Pump wear', blurb: 'Impeller wear cuts output about 1% a day from late October.', wearRate: 0.01, wearStart: 24, warm: { days: 40 } },
  { id: 'dry', name: 'Dry running', blurb: 'March. Water sits close to the pump intake.', startDay: 151, swl0: 85, run: 2.5, warm: { days: 0.4 } },
  { id: 'sensor', name: 'Sensor fault', blurb: 'A pipe joint at 21 m starts returning a false echo.', falseEcho: { d: 21, start: 55 }, warm: { days: 52 } },
].map((s) => ({ ...BASE_SCENARIO, ...s }));

export const DEFAULT_SCENARIO = 1; // over-pumping: the forecast is already warning on load

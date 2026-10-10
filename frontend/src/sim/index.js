export * from './util.js';
export * from './constants.js';
export * from './scenarios.js';
export * from './bores.js';
export * from './simulator.js';
export * from './diagnosis.js';
export * from './alerts.js';
export * from './fleet.js';
export * from './acoustic.js';

import { applyBore, BORES } from './bores.js';
import { SCENARIOS } from './scenarios.js';
import { createSim, warmUp } from './simulator.js';

/** Build and warm up a simulator for a scenario index and bore index. */
export function loadWell(scenarioIdx, boreIdx) {
  const sim = createSim(applyBore(SCENARIOS[scenarioIdx], BORES[boreIdx]));
  warmUp(sim);
  return sim;
}

import { RAIN_MEAN_MM, RAIN_WET_PROB } from './constants.js';
import { dateOf, mulberry32 } from './util.js';

/**
 * Synthetic daily rainfall for one season (366 values, mm/day).
 * Wet days follow the monthly wet-day probability; amounts are exponential
 * around the monthly mean. `monsoonFactor` scales June–September rain.
 */
export function generateRain(seed, monsoonFactor = 1) {
  const r = mulberry32(seed);
  const out = [];
  for (let d = 0; d < 366; d++) {
    const m = dateOf(d * 24 + 12).getMonth();
    const p = RAIN_WET_PROB[m];
    let mm = 0;
    if (r() < p) mm = (RAIN_MEAN_MM[m] / (30.4 * p)) * -Math.log(1 - r() + 1e-9);
    if (m >= 5 && m <= 8) mm *= monsoonFactor;
    out.push(mm);
  }
  return out;
}

/** Long-term normal rainfall for a simulation day (mm/day). */
export const normalRainForDay = (day) => RAIN_MEAN_MM[dateOf(day * 24 + 12).getMonth()] / 30.4;

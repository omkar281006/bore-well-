// Physical constants and calendar markers for the simulated Pune borewell.
// Ranges follow CGWB aquifer mapping of Pune district (deep basalt aquifer,
// storativity ~1e-4, pumping sustainable for 0.5–3 h). See docs in the repo README.

/** Aquifer storativity (dimensionless). */
export const STORATIVITY = 3e-4;
/** Wellbore-storage time constant in days; damps drawdown in the first minutes of a run. */
export const WELLBORE_TAU = 0.006;
/** Radius of influence used to draw the cone of depression (m). */
export const RADIUS_OF_INFLUENCE = 60;
/** Day of the season (from 1 Oct) when the monsoon reaches Pune, ~10 Jun. */
export const MONSOON_ONSET_DAY = 252;
/** Days in one simulated season. */
export const SEASON_DAYS = 365;

/** Monthly mean rainfall for Pune (mm), Jan..Dec, and probability that a day is wet. */
export const RAIN_MEAN_MM = [1, 0, 2, 10, 25, 140, 190, 130, 120, 75, 25, 5];
export const RAIN_WET_PROB = [0.03, 0.02, 0.05, 0.12, 0.2, 0.55, 0.75, 0.65, 0.5, 0.25, 0.1, 0.04];

/** Acoustic sounding parameters (see research report: low-frequency band survives 150 m of 25 mm tube). */
export const ACOUSTIC = {
  sampleRate: 2000, // Hz, simulated after band-limiting
  chirpSeconds: 0.25,
  f0: 60, // Hz
  f1: 250, // Hz
  tubeDispersion: 0.0082, // fractional slow-down of sound in a 25 mm tube at ~250 Hz
  wallLossDbPerM: 0.2, // smooth-wall loss in a 25 mm tube near 100 Hz
  maxDepth: 150, // m
};

/** Speed of sound in the sounding tube (m/s) at air temperature T (°C). */
export const soundSpeed = (tempC) => (331.3 + 0.606 * tempC) * (1 - ACOUSTIC.tubeDispersion);

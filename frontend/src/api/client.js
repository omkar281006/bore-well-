// Backend connection. With no VITE_API_URL the app runs fully in the browser (demo mode).
// With it set, the app can switch to live mode and read the AWS API (or the local Python API):
//   API Gateway -> Lambda (backend/app.py) -> DynamoDB, analysis in backend/analysis.py.
//
// Telemetry contract (schema v2, docs/telemetry-schema.md). One JSON per reading:
// {
//   "well_id": "BW-001",
//   "timestamp": "2027-01-14T06:45:00+05:30",   // any ISO 8601 with a timezone; stored as UTC
//   "data_source": "simulated",                  // simulated | bench-tested | field-measured
//   "depth_to_water_m": 55.62,                   // null while the pump runs (sounding is gated)
//   "temperature_c": 25.8,
//   "pump_state": "OFF",
//   "pump_run_minutes": 0,
//   "measurement_valid": true,
//   "pump_current_a": 0,                         // optional, SCT-013 clamp
//   "echo_tau_ms": 324.1,                        // optional, round-trip time of the water echo
//   "event": "pump_off",                         // optional: pump_on | pump_off | dry_cutoff
//   "fw": "0.4.0"                                // optional firmware version
// }

export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
// ?well=BW-003 in the address bar picks another registered well without rebuilding.
const urlWell = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('well') : null;
export const WELL_ID = (urlWell && /^[A-Za-z0-9_.-]{1,64}$/.test(urlWell) ? urlWell : null) || import.meta.env.VITE_WELL_ID || 'BW-001';
export const HAS_API = Boolean(API_URL);
/** Kept for older imports: 'aws' when an API URL is configured. */
export const MODE = HAS_API ? 'aws' : 'demo';

async function request(path, options = {}) {
  const res = await fetch(API_URL + path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(body.message || `${options.method || 'GET'} ${path} failed with ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

export const health = () => request('/health');

/** Forecast, findings, cycles, daily series and the last 72 h for one well. */
export const getWell = (wellId = WELL_ID, days = 45) => request(`/wells/${encodeURIComponent(wellId)}?days=${days}`);

/** Registered wells with their latest reading. */
export const listWells = () => request('/wells');

/** Status of every registered well: forecast, top finding, days left (the ward radar). */
export const getFleet = (days = 30) => request(`/fleet?days=${days}`);

/** Send readings (the ESP32 and the simulator fleet do this). */
export const postTelemetry = (record) => request('/telemetry', { method: 'POST', body: JSON.stringify(record) });
export const postBatch = (records) => request('/telemetry/batch', { method: 'POST', body: JSON.stringify({ records }) });

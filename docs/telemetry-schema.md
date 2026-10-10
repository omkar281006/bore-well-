# BoreWise telemetry schema (v2)

Every producer (ESP32 firmware, simulator fleet, Streamlit dispatcher) and every consumer
(API, DynamoDB, analysis, web app) uses this record. Validation lives in `backend/schema.py`.

## Example

```json
{
  "well_id": "BW-001",
  "timestamp": "2027-01-14T06:45:00+05:30",
  "data_source": "simulated",
  "depth_to_water_m": 55.62,
  "temperature_c": 25.8,
  "pump_state": "OFF",
  "pump_run_minutes": 0,
  "measurement_valid": true,
  "pump_current_a": 0.0,
  "echo_tau_ms": 323.4,
  "event": "pump_off",
  "fw": "0.4.0"
}
```

While the pump runs the acoustic sounding is gated, so the device sends
`"depth_to_water_m": null, "measurement_valid": false`.

## Fields

| Field | Type | Required | Rule | Meaning |
|---|---|---|---|---|
| `well_id` | string | yes | 1–64 chars, no `#` | Borewell id, e.g. `BW-001` |
| `timestamp` | string | yes | ISO 8601 **with timezone** | Stored in UTC (`...Z`) so the DynamoDB sort key orders correctly |
| `data_source` | string | yes | `simulated`, `bench-tested`, `field-measured` (also `bench_tested`, `field_measured`) | Provenance; underscore spellings are accepted and stored with hyphens. The UI shows it so simulated data is never passed off as field data |
| `depth_to_water_m` | number or null | yes | 0–300 m; null only when `measurement_valid` is false | Wellhead (0 m) down to the water surface; larger = deeper |
| `temperature_c` | number | yes | −10 to 80 °C | Air in the bore; used for the speed-of-sound correction |
| `pump_state` | string | yes | `ON`, `OFF`, `UNKNOWN` | From the motor current. `UNKNOWN` = no pump signal (e.g. clamp unplugged): stored, but never treated as a pump switch and not used by the forecast |
| `pump_run_minutes` | number | yes | ≥ 0 | Minutes into the current run (0 when off) |
| `measurement_valid` | boolean | yes | | False while pumping or when the echo is untrusted |
| `flow_lpm` | number or null | no | 0–5000 L/min | Measured pump flow, if a flow meter is fitted. Stored as null when absent |
| `pump_current_a` | number | no | 0–100 A | SCT-013 clamp RMS current; used for pump-wear and dry-run checks |
| `echo_tau_ms` | number | no | 0–2000 ms | Round-trip time of the water echo |
| `event` | string | no | `pump_on`, `pump_off`, `dry_cutoff` | Sent the moment the pump switches; `dry_cutoff` when the dry-run relay tripped |
| `fw` | string | no | ≤ 64 chars | Firmware version |
| `scenario` | string | no | ≤ 64 chars | Simulator scenario name (simulated data only) |

## Added by the server

| Field | Meaning |
|---|---|
| `received_at` | UTC time the API stored the record |
| `stale` | `true` when a `bench-tested` or `field-measured` reading arrives more than `STALE_AFTER_HOURS` (default 24 h, a stack parameter) after its `timestamp`. Stale readings are stored and shown, but excluded from cycles and the forecast. `simulated` backfills are exempt because their timestamps are a model clock |
| `schema_version` | `2` |

## Cadence (what the analysis expects)

- heartbeat every 15 minutes
- an event record when the pump starts and when it stops
- a valid reading every 2 minutes for the first hour after the pump stops (the refill curve)

## Well registration (`POST /wells`)

```json
{
  "well_id": "BW-001",
  "name": "Sahyadri Heights CHS, Baner",
  "bore_type": "open",
  "depth_m": 120,
  "intake_m": 103,
  "min_submergence_m": 2.0,
  "pump_flow_m3_day": 172.8,
  "fractures": [{"d": 22}, {"d": 48}, {"d": 76}, {"d": 98}],
  "rain_mm": {"2027-06-10": 12.4}
}
```

`bore_type` is one of `open`, `screen`, `dug`, `hand`. The forecast threshold is `intake_m − min_submergence_m`
(default 2 m): the deepest water level at which the pump still has enough water above its intake.
Demo profiles live in `config/wells.json`; `python -m simulator.fleet --api <url> --config config/wells.json` registers and backfills them. `fractures` come from the driller's log (optional).
`rain_mm` is daily rainfall for the well's location (IMD gridded data in production); it enables the weak-monsoon check.

## Validation behaviour

- missing required field, wrong type, bad enum, out-of-range value, or a timestamp without a timezone: HTTP 400 with the reason
- a `bench-tested` / `field-measured` timestamp more than 10 minutes in the future: HTTP 400 (device clock not synced)
- a late device reading: accepted (201) with `stale: true` in the response
- `/telemetry/batch` accepts up to 500 records; valid ones are stored and the response lists rejected indexes (HTTP 207 when mixed)

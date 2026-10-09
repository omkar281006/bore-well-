# BoreWise Shared Telemetry Schema Definition

All components across BoreWise (Python simulator, ESP32 firmware, AWS Lambda ingestion API, DynamoDB persistence, and Streamlit dashboard) strictly communicate using this unified telemetry JSON specification.

## JSON Telemetry Payload Example

```json
{
  "well_id": "BW-001",
  "timestamp": "2026-10-10T09:00:00Z",
  "data_source": "simulated",
  "depth_to_water_m": 48.2,
  "temperature_c": 28.5,
  "pump_state": "OFF",
  "pump_run_minutes": 42,
  "measurement_valid": true
}
```

## Field Specification Table

| Field Name | Data Type | Valid Range / Format | Description |
|---|---|---|---|
| `well_id` | String | Non-empty string | Unique identifier for the monitored borewell (e.g., `"BW-001"`). |
| `timestamp` | String | ISO 8601 UTC string | Timestamp of telemetry sample (`"YYYY-MM-DDTHH:MM:SSZ"`). |
| `data_source` | String | `"simulated"`, `"bench-tested"`, `"field-measured"` | Provenance label indicating origin of telemetry reading. |
| `depth_to_water_m` | Float | `0.0` to `300.0` metres | Distance from ground casing top (0.0m) down to water surface. Higher values represent deeper drawdown. |
| `temperature_c` | Float | `-10.0` to `80.0` °C | Ambient/water temperature. |
| `pump_state` | String | `"ON"`, `"OFF"` | Operational status of borewell pump. |
| `pump_run_minutes` | Float | `>= 0.0` | Duration pump has been running continuously in minutes. |
| `measurement_valid` | Boolean | `true`, `false` | Integrity flag indicating sensor confidence or telemetry quality. |

## Validation & Boundary Enforcement Rules

The ingestion module `backend/schema.py` enforces:
1. Rejection of payloads with missing required keys with HTTP `400 Bad Request`.
2. Strict type checking (rejecting string values in numeric fields or invalid enum strings).
3. Physical bound checking: Depth must be between 0.0m and 300.0m; Temperature must be between -10°C and 80°C.

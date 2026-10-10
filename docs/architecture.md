# BoreWise architecture

```
 ESP32 at the wellhead            Simulator fleet (python -m simulator.fleet)
 (firmware/esp32)                 same physics as the web app, ECS Fargate later
        │  POST /telemetry/batch              │
        └──────────────┬──────────────────────┘
                       ▼
        API Gateway HTTP API  (backend/template.yaml)
                       │
                       ▼
        Lambda  backend/app.py   ── schema.py   validate + normalise timestamps to UTC
                       │          ── analysis.py cycles, refill fit, forecast, findings
                       │          ── storage.py  DynamoDB (or in-memory locally)
                       ▼
        DynamoDB  PK well_id · SK timestamp  (well registration at SK "#META")
                       │
         GET /wells/{id}│                         GET /telemetry
                       ▼                                 ▼
        Web app (frontend/)                       Streamlit dashboard (dashboard/)
        3D cutaway, forecast, findings,           engineering view: raw readings,
        alerts in en / mr / hi                    cycle table, short-horizon bands
```

## One physics model

`frontend/src/sim/` (JavaScript) and `simulator/physics.py` (Python) are the same model; a test
(`tests/test_simulator.py::test_matches_web_app_engine`) checks they agree to 1 mm. The web app's
demo mode runs it in the browser; the fleet runs it in Python and posts telemetry.

## Analysis on real readings

`backend/analysis.py` only uses what a device sends, so it works for simulated, bench and field data:

1. split the stream into pump cycles from `pump_state` changes
2. drawdown at switch-off, Theis recovery fit on readings 45+ minutes after switch-off → transmissivity,
   specific capacity, mean motor current
3. daily pre-pump water table and deepest level
4. dry-up forecast: 21-day trend against `intake − 2 m`, P10/P50/P90 dates, pumping cut that reaches 10 June
5. findings with message keys the web app translates (en / mr / hi)

| Finding | Signature in the data |
|---|---|
| Dry before the monsoon | P50 date before 10 June |
| Pump cut off / running dry | `dry_cutoff` event, or current < 75% of normal while ON |
| Fracture dewatered | transmissivity down > 35% in a week while the level fell past a fracture |
| Well clogging | drawdown per run rising faster than transmissivity falls |
| Pump wear | smaller drawdown and lower current, aquifer unchanged |
| Neighbour interference | level falls > 45 cm while our pump has been off 2.5 h+ |
| Weak monsoon | rain since 1 June < 65% of normal (needs `rain_mm` on the well) |
| Sensor fault | two runs that move the reading < 8 cm |

Validated on simulated telemetry for 4 bore types × 9 scenarios: 31 of 36 combinations caught.
The hand-pump bore is the weak spot: a hand stroke barely moves the water, so wear, clogging,
fracture and sensor faults are not visible there.

## AWS services

| Service | Use |
|---|---|
| API Gateway (HTTP API) | public endpoint, CORS |
| Lambda (Python 3.12, arm64) | ingestion, validation, analysis |
| DynamoDB | telemetry and well records |
| CloudWatch | Lambda error alarm, logs |
| Amplify Hosting | the built web app (`frontend/dist`) |
| ECS Fargate (planned) | always-on simulator fleet |
| SNS / WhatsApp (planned) | alerts from findings |
| Strands Agents (planned) | explanations in Marathi / Hindi |

# BoreWise: know the day your borewell runs dry

**AWS Environment Hackathon, Delhi, 8–11 October 2026 · Track: Heat and Water (groundwater and droughts)**

| | |
|---|---|
| Repository | https://github.com/omkar281006/bore-well- |
| Live API (AWS) | `[DEPLOYED_API_URL]` (try `/health` and `/wells/BW-001`) |
| Web app | `[WEB_APP_URL or "run locally: frontend/README in section 8 of README.md"]` |
| Demo video (≤ 3 min) | `[VIDEO_URL]` |
| Deployment evidence | [`docs/deployment-evidence.md`](docs/deployment-evidence.md) |

> Fill the four brackets after the deploy, then delete this line.

## 1. Problem and users

Housing societies and farm cooperatives around Pune pump their borewells blind. They learn a well is failing
only when the pump starts sucking air. By then the motor may have burnt out running dry (₹7,000–19,000 for a
1–3 HP submersible), the society is buying tankers (about ₹1,000 a load, rising to about ₹2,000 in 2026; one
Pune society spent about ₹7.5 lakh in a season), and nobody knows whether the cause is the aquifer, the well,
the pump or a neighbour.

Pune's deep Deccan-basalt aquifers sustain pumping for only 0.5–3 hours (CGWB aquifer mapping), and in
May 2026, 11 of the district's 13 talukas were below their five-year May water level. Nationally, 730 of
6,762 assessment units are over-exploited (GWRA 2025), while Atal Bhujal has about 3,900 working metered
wells against a 50,000 target.

**Users:** society secretaries and facility managers, farm co-operatives, and the ward or taluka officers
who plan tanker supply.

## 2. Solution

Every pump cycle is a free aquifer test. BoreWise reads the water level at the wellhead (an acoustic echo
down a 25 mm sounding tube, temperature-corrected), gates readings while the pump runs, and then:

1. **Fits the refill curve** after each pump-off (Theis recovery) to estimate transmissivity and specific capacity.
2. **Tracks the pre-pump water table** day by day and forecasts the date the level reaches the pump's
   safe threshold (intake minus minimum submergence), with P10/P50/P90 dates.
3. **Tells the user what to do:** how much to cut pumping to last until the monsoon (10 June).
4. **Diagnoses the cause**, which decides the fix: depletion, dry running, a dewatered fracture, well
   clogging, pump wear, neighbour interference, a weak monsoon, or a faulty sensor.
5. **Speaks the user's language:** alerts in English, Marathi and Hindi.

Target hardware cost is about ₹2,000–2,500 per well, against US$1,700–2,900 for imported sonic meters.

## 3. What we built

| Part | What it does | Where |
|---|---|---|
| Web app | 3D cutaway of the borewell and aquifer, live depth, forecast, findings, refill and echo charts, ward fleet; demo mode (in-browser simulator) and Live API mode | `frontend/` |
| Physics simulator | Cooper–Jacob drawdown with wellbore storage, skin, fracture-controlled transmissivity, recharge; 10 scenarios × 4 bore types; Python and JavaScript versions agree to 1 mm | `simulator/`, `frontend/src/sim/` |
| API and analysis | Validation (schema v2), storage, cycle splitting, recovery fit, forecast, findings; stale and unknown-state readings excluded from the forecast | `backend/` |
| Fleet | Simulated wells post ESP32-style telemetry to the API; 3 demo wells from `config/wells.json` | `simulator/fleet.py` |
| Engineering dashboard | Raw readings, cycle table, forecast bands, test dispatcher | `dashboard/` (Streamlit) |
| Firmware | ESP32: NTP time, pump current (SCT-013), gated sounding, batched upload | `firmware/esp32/` |
| Deploy kit | One-command deploy, scoped IAM policy, budget alert, smoke test that writes evidence | `infra/`, `scripts/smoke_test.py` |

## 4. AWS usage

```
ESP32 / simulator fleet ──POST /telemetry/batch──► API Gateway (HTTP API, throttled)
                                                         │
                                                         ▼
                                Lambda (Python 3.12, arm64): validate → store → analyse
                                                         │
                                                         ▼
                           DynamoDB (on-demand; PK well_id, SK timestamp)
                                                         │
                        GET /wells/{id} ◄────────────────┘──────► web app / Streamlit
```

| Service | Use |
|---|---|
| AWS SAM (open-source) | Infrastructure as code: `backend/template.yaml`, `backend/samconfig.toml` |
| Amazon API Gateway (HTTP API) | Public endpoint, CORS, 20 req/s throttle |
| AWS Lambda | Ingestion, validation and analysis in one Python function |
| Amazon DynamoDB | Telemetry and well registrations, single table, on-demand |
| Amazon CloudWatch | Logs (14-day retention), alarm on Lambda errors |
| AWS IAM | Scoped deployer user; Lambda role limited to its own table |
| AWS Budgets | 5 USD/month alert |
| `[AWS Amplify Hosting]` | `[Hosted web app, if done; otherwise delete this row]` |

Region `ap-south-1` (Mumbai). Cost for the hackathon: under 1 USD.

## 5. Evaluation (only tests we actually ran)

| Check | Result |
|---|---|
| Python test suite | 36 / 36 pass |
| Web app simulator tests | 5 / 5 pass |
| Live AWS smoke test (`docs/deployment-evidence.md`) | `[18 / 18]` against the deployed API, DynamoDB store |
| Fault detection, 4 bore types × 9 scenarios, on device-style telemetry | 31 / 36 caught |
| Acoustic depth, simulated, 161 pings | mean bias 0.2 cm, worst 4.6 cm |
| Transmissivity from the refill fit | within about 25% of the simulator's true value |
| Bad input | missing fields, out-of-range depth, no timezone, bad enum, future device clock, malformed JSON all rejected (HTTP 400); late readings stored but flagged `stale` and kept out of the forecast |

Misses: on a hand-pump bore a stroke barely moves the water, so clogging, wear, fracture and sensor faults
are not visible there; pump wear is also missed on the dug-cum-bore well.

## 6. Limitations (honest status)

| Item | Status |
|---|---|
| Data | **All results use simulated data.** Field accuracy is unknown. |
| Acoustic sounder | Designed and simulated; not built or bench-tested |
| ESP32 firmware | Written; `[not compiled or flashed / bench-tested: describe]` |
| Weak-monsoon check | Needs daily rainfall per well (IMD gridded data in production) |
| Marathi / Hindi text | Needs a native-speaker review |

## 7. Next step

A dipper-calibrated pilot in 5–10 Pune society borewells and a few Purandar/Baramati farm bores. We will compare
BoreWise's water level with a manual dipper reading after each pump cycle, then check the dry-date forecast
against what actually happens before the monsoon.

## Team

`[Names and roles]`

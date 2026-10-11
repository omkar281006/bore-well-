# BoreWise

**Every pump cycle is an aquifer test.** BoreWise listens to a borewell, reads how fast it refills after
each pump run, diagnoses what is going wrong, and forecasts the day it will run dry, early enough for a
housing society or farm cooperative to ration water instead of paying for tankers or a burnt pump.

Built for the AWS city-problems hackathon, **Heat and Water track** (groundwater and droughts), by a
team from VIT Pune. Repo: <https://github.com/mahendraSpatil/borewise>.

---

## Contents

1. [The problem](#1-the-problem)
2. [How the idea evolved](#2-how-the-idea-evolved)
3. [The core insight](#3-the-core-insight)
4. [How BoreWise works](#4-how-borewise-works)
5. [What we built](#5-what-we-built)
6. [Architecture and AWS](#6-architecture-and-aws)
7. [Repository layout](#7-repository-layout)
8. [Run it](#8-run-it)
9. [API and telemetry format](#9-api-and-telemetry-format)
10. [Testing and validation results](#10-testing-and-validation-results)
11. [Merging the two codebases](#11-merging-the-two-codebases)
12. [Research summary](#12-research-summary)
13. [Limitations](#13-limitations)
14. [Roadmap](#14-roadmap)
15. [Numbers for the pitch](#15-numbers-for-the-pitch)
16. [Team and credits](#16-team-and-credits)

---

## 1. The problem

Pune housing societies and farm cooperatives pump their borewells blind. They find out a well is
failing only when it starts sucking air. By then:

- the pump may already have burnt out running dry (a 1–3 HP borewell submersible costs about ₹7,000–19,000),
- the society is buying private tankers for the rest of the summer (about ₹1,000 a load rising to about
  ₹2,000 in 2026; one Pune society spent about ₹7.5 lakh in a single season),
- and nobody knows whether the problem is the aquifer, the well, the pump or the neighbours.

Deep Deccan-basalt aquifers around Pune store very little water and can sustain pumping for only
**0.5–3 hours** (CGWB aquifer mapping, Pune). In May 2026, 11 of Pune district's 13 talukas had water
levels below their five-year May average.

## 2. How the idea evolved

| Stage | What we decided | Why |
|---|---|---|
| Track choice | Heat and Water, groundwater and droughts | Real, local, money-backed pain; few teams pick it |
| First pitch | "Thermo-Acoustic Borewell Yield Predictor": drop an ESP32 down the shaft | Original team idea |
| Reality check | Sensor stays **at the wellhead** and sounds down a 25 mm PVC tube | A working borewell is full of pump, riser pipe and cable; nobody risks a ₹50k pump for a sensor |
| | Acoustic **echo sounding**, not an ultrasonic module | Water is 30–150 m down; a JSN-SR04T reaches about 4.5 m |
| | Temperature is for **speed-of-sound correction** | About 0.17% depth error per °C |
| | GRACE-FO only as regional context | It is monthly and about 300 km per pixel |
| | Timestream dropped | Closed to new AWS customers since June 2025 |
| Upgrade | **Treat every pump cycle as an aquifer test** | Turns a level gauge into a diagnostic tool (see below) |
| Build plan | Simulate the hardware first, physics-based | Removes the riskiest part; lets us test many failures |
| Validation | Inject 9 failure types into simulated wells and score detection | Shows judges evidence, not just a demo |
| Name | BoreWise | Easier to remember than the thesis-style title |

## 3. The core insight

The acoustic sensor is not the new part: oilfield "echometers" have done echo sounding for decades and
imported sonic water-level meters cost US$1,700–2,900. What nobody does is **read the pump cycles a
society already runs every day**.

When the pump stops, the water level climbs back. How fast it climbs is a free pump test:

- the **Theis recovery** slope gives the aquifer's **transmissivity** (how easily water flows in),
- the drop at switch-off gives the **specific capacity** and the **well loss** (clogging),
- the motor current gives the **pump's health**,
- the settled level before each run, day after day, gives the **seasonal decline**.

Watching how these change over weeks separates problems that look the same from the surface:

| Problem | Water table | Refill slope (T) | Drawdown per run | Motor current | Right action |
|---|---|---|---|---|---|
| Seasonal depletion | falling | steady | steady | steady | ration until the monsoon |
| Fracture dewatered | falls past a fracture | **drops sharply** | grows | steady | shorter, spaced-out runs |
| Well clogging | steady | steady | **grows** | steady | clean the well; rationing won't help |
| Pump wear | steady | steady | **shrinks** | **drops** | service the pump |
| Neighbour interference | **falls while our pump is off** | — | — | — | agree pumping times |
| Dry running | at the intake | — | — | **drops** | stop the pump now |
| Sensor fault | reading stuck | — | **near zero** | normal | check the sounding tube |

## 4. How BoreWise works

1. **Chirp.** A 60–250 Hz log chirp goes down a 25 mm sounding tube. Low tones survive the 150 m round
   trip; kHz tones die in the tube (about 61 dB loss at 100 Hz vs 193 dB at 1 kHz over 150 m).
2. **Echo.** Cross-correlation (matched filtering) finds the echo off the water. A time-varying gain undoes
   tube loss; parabolic interpolation refines the peak. Depth = c·τ/2 with
   c = (331.3 + 0.606·T) × (1 − 0.0082) for temperature and tube width. Readings are taken only while the
   pump is off.
3. **Refill.** After each run, a reading every 2 minutes for an hour. The points 45+ minutes after
   switch-off are fitted on a Theis recovery plot (residual drawdown vs log₁₀ t/t′).
4. **Forecast.** A 21-day trend of the pre-pump water table, plus typical drawdown, against the pump intake
   (minus 2 m of safety) gives P10/P50/P90 dry-up dates and the pumping cut that carries the well to the
   monsoon (about 10 June).
5. **Diagnose and alert.** Findings are ranked by severity and written as WhatsApp-style alerts in
   **English, Marathi and Hindi**.

## 5. What we built

### Web app (`frontend/`)
A React + Three.js app, the face of the project:

- **3D cutaway** of a Deccan-basalt borewell: lava-flow layers (vesicular basalt, red bole, massive basalt),
  the water table with its live cone of depression, water-bearing fractures that glow and go grey when
  dewatered, a society building, rain during the monsoon, and a depth ruler.
- **Realistic bore models, 4 types:** open-hole borewell (steel casing, bare basalt), screened tubewell
  (PVC, slotted screens, gravel pack, bentonite seal), dug-cum-bore well (stone-lined dug well), and
  India Mark II hand pump (animated handle and rods). Every part is labelled when the camera is close:
  submersible motor, impeller stages, non-return valve, riser, cable, gauge, check valve, gate valve,
  starter panel with run and dry-run lamps, the BoreWise unit with its solar panel.
- **9 failure scenarios:** healthy, over-pumping, fracture dewatering, neighbour interference, clogging,
  weak monsoon, pump wear, dry running, sensor fault.
- **Panels:** depth HUD, dry-up forecast with P10–P90 timeline and one-click rationing, diagnosis, season
  chart, last 72 hours, Theis recovery fit, acoustic echo with the working shown, ward groundwater radar of
  36 society wells, alert preview in three languages, KPI counters, live telemetry ticker.
- **Experience:** sonar intro and camera dive, bloom-lit water and pings, flowing fracture particles,
  camera presets, day/night, glass panels, tilt cards, sound (the real chirp pitched up so laptops can play
  it), **light and dark mode**, reduced-motion support, phone layout.
- **Demo / Live API switch:** demo runs the simulator in the browser; live reads the real API.

### Backend (`backend/`)
- One Python router for **AWS Lambda** and a **local server**.
- Schema v2 validation, timestamps normalised to UTC, batch ingest (up to 500 readings).
- **Analysis engine** (`analysis.py`) that works only from what a device sends: cycle detection, recovery
  fit, daily series, dry-up forecast and all findings.
- Storage: DynamoDB single table (PK `well_id`, SK `timestamp`, well registration at `#META`), with an
  in-memory store (optionally saved to disk) for local runs.
- **SAM template** (`template.yaml`): HTTP API, Lambda (Python 3.12, arm64), DynamoDB, CloudWatch alarm.

### Simulator (`simulator/`)
- `physics.py`: the same model as the web app (a test checks they agree to 1 mm): Cooper-Jacob drawdown
  with wellbore storage, superposition over pump runs, well loss, fracture-controlled transmissivity,
  seasonal decline, monsoon recharge from synthetic Pune rainfall, neighbour interference, pump wear.
- `telemetry.py`: emits exactly what the ESP32 sends (heartbeats, pump events, refill readings, gated depth).
- `fleet.py`: posts one or many simulated wells to the API, with a live-streaming mode.
- `simulator.py` and `forecast.py`: the original teammate API for the Streamlit dashboard, rebuilt on the
  shared physics.

### Streamlit dashboard (`dashboard/`)
Engineering view: raw telemetry, cycle table, short-horizon P10/P50/P90 bands, a test dispatcher for the API.

### Firmware (`firmware/esp32/`)
NTP timestamps, SCT-013 current clamp (true RMS), optional DS18B20, gated sounding, 15-minute heartbeats,
pump events, 2-minute refill readings, buffered batch upload. The acoustic sounder function is stubbed and
simulated data is labelled `simulated`.

### Research (`docs/research-report.md`)
A full report: acoustic physics, hardware, Deccan-basalt hydrogeology, pump-test equations, failure
signatures, Indian data sources, forecasting and validation methods, AWS costs, market numbers,
competitors, a master parameter table and an improvement roadmap.

### Prototype (`prototype/`)
The single-file HTML version the web app grew from. Also published as a claude.ai artifact.

## 6. Architecture and AWS

```
 ESP32 at the wellhead            Simulator fleet (python -m simulator.fleet)
        │  POST /telemetry/batch              │
        └──────────────┬──────────────────────┘
                       ▼
        API Gateway HTTP API  ──►  Lambda (backend/app.py)
                                     ├─ schema.py    validate, normalise to UTC
                                     ├─ analysis.py  cycles, refill fit, forecast, findings
                                     └─ storage.py   DynamoDB (in-memory locally)
                       │
        GET /wells/{id}│                         GET /telemetry
                       ▼                                 ▼
        Web app (frontend/, Amplify Hosting)      Streamlit dashboard
```

| AWS service | Role | Status |
|---|---|---|
| API Gateway (HTTP API) | public endpoint, CORS | in template |
| Lambda | ingestion, validation, analysis | in template |
| DynamoDB | telemetry and well records | in template |
| CloudWatch | error alarm, logs | in template |
| Amplify Hosting | web app | build ready (`npm run build`) |
| ECS Fargate | always-on simulator fleet | planned (same `fleet.py`) |
| SNS / WhatsApp (End User Messaging) | alerts | planned; SMS to India needs DLT registration |
| Strands Agents SDK | Marathi/Hindi explanations | planned; templates already in the app |
| SAM CLI | build and deploy | used |

Prize rule check: deployed on AWS and uses AWS open-source tooling (SAM CLI), so it is eligible.

## 7. Repository layout

```
borewise/
├── frontend/            React + Three.js web app
│   ├── src/sim/         JS simulator, diagnosis, acoustics, alerts, ward fleet (no DOM)
│   ├── src/scene/       3D cutaway, bore models, procedural textures
│   ├── src/charts/      canvas charts
│   ├── src/live/        API → app adapter for live mode
│   ├── src/hooks/       one animation loop, theme, toasts
│   ├── src/components/  UI
│   └── scripts/validate.mjs   36-case sweep
├── backend/             app.py, schema.py, analysis.py, storage.py, template.yaml
├── simulator/           physics.py, telemetry.py, fleet.py, simulator.py, forecast.py
├── dashboard/           Streamlit app
├── firmware/esp32/      main.cpp, wiring and flashing guide
├── config/wells.json    3 demo well profiles (intake, submergence, scenario)
├── infra/               deploy.ps1, scoped IAM policy, budget alert, deploy guide
├── scripts/smoke_test.py  18-check test of a deployed API → docs/deployment-evidence.md
├── tests/               35 pytest tests
├── docs/                research report, architecture, telemetry schema, limitations, teammate's original README
├── data/                sample CSV; local API data goes in data/local_store/
├── prototype/           single-file HTML prototype
└── requirements.txt
```

## 8. Run it

Needs **Node.js 18+** and **Python 3.10+**. Windows commands shown; macOS/Linux are the same with `/`.

**Web app only (demo mode)**
```powershell
cd D:\borewise\frontend
npm install
npm run dev            # http://localhost:5173
```

**Full pipeline (three terminals)**
```powershell
# 1. Python packages (once)
cd D:\borewise
pip install -r requirements.txt

# 2. API  → http://localhost:8000
python backend/app.py

# 3. Simulated well: 30 days of history, then live streaming
python -m simulator.fleet --api http://localhost:8000 --scenario overpump --days 30 --live

# 4. Web app: set VITE_API_URL=http://localhost:8000 in frontend/.env (copy .env.example)
cd frontend
npm run dev            # use the Demo / Live API switch in the header
```

Scenarios: `healthy, overpump, fracture, interf, clog, weak, wear, dry, sensor, weak_recharge`.
Bores: `--bore open | screen | dug | hand`. Several wells: `--scenario healthy,clog,interf`.

**Streamlit dashboard**
```powershell
streamlit run dashboard/app.py
```

**Deploy to AWS** (full guide: `infra/README.md`; scoped IAM user first, never root)
```powershell
$env:AWS_PROFILE = "borewise"
powershell -ExecutionPolicy Bypass -File infra\deploy.ps1 -Email you@example.com
```
Budget alert, `sam build` + `sam deploy` (ap-south-1), `frontend/.env`, the 3 demo wells and the
evidence file `docs/deployment-evidence.md`, in one go.
Use the `ApiUrl` output as `VITE_API_URL`, as `--api` for the fleet and as `API_BASE` in the firmware.
Host `frontend/dist` (from `npm run build`) on Amplify. DynamoDB on-demand costs about 1.25 USD per
million writes; a 30-day backfill is roughly 6,000 writes.

## 9. API and telemetry format

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | service check |
| POST | `/telemetry` | one reading |
| POST | `/telemetry/batch` | up to 500 readings |
| GET | `/telemetry?well_id=BW-001` | latest readings |
| GET | `/wells` | registered wells |
| POST | `/wells` | register a well (bore type, depth, intake, pump flow, fractures, rainfall) |
| GET | `/wells/{id}?days=45` | forecast, findings, cycles, daily series, last 72 h |

One reading (full rules in `docs/telemetry-schema.md`):

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

While the pump runs: `"depth_to_water_m": null, "measurement_valid": false`.
`data_source` is always shown in the app so simulated data is never presented as field data.

## 10. Testing and validation results

| Check | Result |
|---|---|
| Python test suite (`python -m pytest tests`) | 36 / 36 pass |
| API smoke test (`scripts/smoke_test.py`, local rehearsal) | 18 / 18 pass; AWS run pending deploy |
| Web app simulator tests (`npm test`) | 5 / 5 pass |
| Web app engine sweep (`npm run validate`), 4 bores × 9 scenarios | 31 / 36 caught |
| Backend analysis on device-style telemetry, 4 × 9 | 31 / 36 caught |
| Acoustic depth (simulated), 161 pings | mean bias 0.2 cm, worst 4.6 cm |
| Transmissivity from the refill fit | within about 25% of the simulator's true value |
| Python physics vs JS physics | agree to 1 mm |
| Forecast stability (old bug) | same risk level hour to hour |
| End-to-end: fleet → API → analysis → web app | verified in a headless browser |

Misses: on the hand-pump bore a stroke barely moves the water, so clogging, wear, fracture and sensor
faults are not visible there; pump wear is also missed on the dug-cum-bore well.

## 11. Merging the two codebases

The teammate repo (`omkarbachhav24-ux/borewise`) supplied the backend, schema, simulator, forecast,
Streamlit dashboard, firmware, tests and docs. Problems found and fixed during the merge:

| Problem | Effect | Fix |
|---|---|---|
| `Tuple` not imported in `backend/app.py` | backend crashed on start; 4 of 9 tests never ran | import fixed, backend extended |
| Drawdown grew with depth | over-pumping reached **860 m** in 72 h | rebuilt on bounded shared physics |
| Trend from first and last reading | same data said Normal, Warning, High Risk an hour apart | trend from settled pre-pump levels |
| Fixed timestamp in firmware | every reading had the same time | NTP time |
| Fake depth sweep labelled `bench-tested` | misleading provenance | labelled `simulated` |
| Streamlit API mode | data lost on every click; crash on pumping rows | session state, last valid depth |

Bugs found in our own work and fixed:

- The published prototype's 3D view never loaded (script-order error); fixed and checked in a browser.
- The acoustic depth finder read 0.5–0.7 m too deep (envelope peak offset); now within 5 cm.

## 12. Research summary

Full report with sources: `docs/research-report.md`. Key points:

- **Acoustics:** use 60–250 Hz; correct for temperature (about 0.17%/°C) and tube width (−0.3 to −0.8%);
  sound only with the pump off; a cheap build looks comfortable to 80–100 m and marginal at 150 m.
- **Hardware (about ₹2–2.5k):** ESP32, INMP441 I2S mic, MAX98357A amp, DS18B20, SCT-013 clamp, 25 mm PVC tube.
- **Hydrogeology (CGWB Pune):** deep aquifer at 48–175 m, storativity about 10⁻⁴, transmissivity tens of
  m²/day, recharge 4–15% of rainfall, pumping sustainable for 0.5–3 h.
- **Data:** CGWB/India-WRIS well levels are quarterly (good for calibrating seasons, not daily forecasts);
  IMD gridded rainfall via `imdlib`; GRACE-FO for regional context only.
- **AWS:** free tier plus up to $200 credits covers the demo; Timestream LiveAnalytics closed to new
  customers; LocalStack Community retired in March 2026; SMS to India needs DLT registration.
- **Competitors:** none found that combines cheap continuous level sensing, a dry-up forecast and pump
  protection. Closest: Waterlab "Bhujal" (estimates without a sensor), WEGoT (flow meters), imported sonic
  meters, government DWLRs.

## 13. Limitations

- Everything is validated on **simulated data only**; field accuracy is unknown.
- The acoustic sounder is not built yet (firmware function is a stub).
- No published measurement exists of a low-cost mic-and-speaker setup in a tube deeper than about 100 m.
- Weak-monsoon detection needs daily rainfall on the well record (IMD in production).
- Marathi and Hindi alert text needs a native-speaker check before the pitch.
- Streamlit dashboard and firmware were not run in our test environment (syntax-checked only).

More in `docs/limitations.md`.

## 14. Roadmap

**Now (hackathon)**
1. Deploy the SAM stack and host the web app on Amplify for a live judge URL.
2. Bench test: a 30–60 m coiled PVC pipe to measure real echo strength.
3. Strands agent for Marathi/Hindi explanations; WhatsApp alert demo.
4. Run the simulator fleet on ECS Fargate with a ward of wells.

**After**
5. Dipper-calibrated pilot in 5–10 Pune society borewells and Purandar/Baramati farm bores.
6. Pump current as the only sensor for a cheaper tier.
7. Automatic dry-run cut-off and smart scheduling via a relay board.
8. Recharge-pit recommendations and before/after checks (Jalyukt Shivar, rooftop harvesting).
9. Open-data export to CGWB / Atal Jal; tamper-evident logs for future water credits.
10. LoRaWAN and solar variant for farms.

## 15. Numbers for the pitch

| Claim | Number |
|---|---|
| National stress | ~247 BCM/yr extracted, 60.6% of extractable; 730 of 6,762 units over-exploited (GWRA 2025) |
| Local stress | 11 of 13 Pune talukas below their 5-year May average (May 2026) |
| Why basalt wells fail fast | deep Pune aquifer sustains pumping for only 0.5–3 h |
| Society pain | private tanker ~₹1,000 → ~₹2,000 a load in 2026; ₹7.5 lakh in one season at one society |
| Monitoring gap | 3,892 working metered wells vs a 50,000 target (Atal Bhujal) |
| Price disruption | ~₹2–2.5k of parts vs US$1,700–2,900 imported sonic meters |
| Payback | one avoided tanker a week ≈ ₹78k–1 lakh a year |

Sources for each are in `docs/research-report.md`.

## 16. Team and credits

| Area | Files |
|---|---|
| Simulation and forecast | `simulator/`, `frontend/src/sim/` |
| AWS backend | `backend/` |
| Web app and dashboard | `frontend/`, `dashboard/` |
| Hardware and QA | `firmware/esp32/`, `tests/`, `docs/` |

The original MVP came from the teammate repo
[omkarbachhav24-ux/borewise](https://github.com/omkarbachhav24-ux/borewise); its history is preserved in
this repo. The 3D web app, shared physics, analysis engine, research and merge fixes were added on top.

**Push updates**
```powershell
git add -A
git commit -m "Describe the change"
git push
```

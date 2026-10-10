# BoreWise

Acoustic borewell monitoring for Pune housing societies and farm cooperatives.
Every pump cycle is an aquifer test: BoreWise reads the water level, fits the refill curve,
diagnoses what is going wrong and forecasts the day the borewell runs dry.

Built for the AWS city-problems hackathon, Heat and Water track (groundwater and droughts).

## What is in here

| Folder | What it is |
|---|---|
| `frontend/` | Web app: 3D borewell digital twin, dry-up forecast, findings, alerts in English / Marathi / Hindi. Demo mode runs the simulator in the browser; live mode reads the API |
| `backend/` | API (one Python router for Lambda and a local server), validation, analysis engine, DynamoDB storage, SAM template |
| `simulator/` | Python physics (same model as the web app), ESP32-style telemetry stream, fleet that posts to the API, the original short-horizon forecast |
| `dashboard/` | Streamlit engineering dashboard (raw readings, cycle table, P10/P50/P90 bands, test dispatcher) |
| `firmware/esp32/` | ESP32 telemetry firmware (NTP time, pump current, gated sounding, batched upload) |
| `tests/` | 25 pytest tests: simulator, forecast, schema, API, end-to-end analysis |
| `docs/` | Architecture, telemetry schema, limitations, the teammate's original README |
| `data/` | Sample CSV; `data/local_store/` holds the local API's data |
| `prototype/` | The single-file HTML prototype, for reference |

## Run everything on Windows

Needs Node.js 18+ and Python 3.10+.

**1. Python packages (once)**

```powershell
cd D:\borewise
pip install -r requirements.txt
```

**2. Start the API** (terminal 1)

```powershell
cd D:\borewise
python backend/app.py
```

Runs at http://localhost:8000 and keeps data in `data/local_store/`.

**3. Feed it a simulated well** (terminal 2)

```powershell
cd D:\borewise
python -m simulator.fleet --api http://localhost:8000 --scenario overpump --days 30 --live
```

This backfills 30 days of an over-pumping society well, then keeps streaming new readings.
Other scenarios: `healthy, fracture, interf, clog, weak, wear, dry, sensor, weak_recharge`.
Bore types: `--bore open | screen | dug | hand`.

**4. Start the web app** (terminal 3)

```powershell
cd D:\borewise\frontend
copy .env.example .env      # then set VITE_API_URL=http://localhost:8000
npm install                 # first time only
npm run dev
```

Open http://localhost:5173. The **Demo / Live API** switch in the header changes between the
in-browser simulator (9 scenarios, 4 bore types) and the real pipeline.

**5. Optional: Streamlit dashboard**

```powershell
cd D:\borewise
streamlit run dashboard/app.py
```

Choose "AWS Endpoint / Local API", keep `http://localhost:8000/telemetry`, click Fetch.

## Tests

```powershell
cd D:\borewise
python -m pytest tests -v                 # 25 Python tests
cd frontend; npm test; npm run validate   # simulator unit tests and the 36-case sweep
```

## Deploy to AWS

```powershell
cd D:\borewise\backend
sam build
sam deploy --guided        # region ap-south-1 (Mumbai) is closest to Pune
```

Use the `ApiUrl` output for `VITE_API_URL` in `frontend/.env`, for `--api` in the fleet, and for
`API_BASE` in the firmware. Build the web app with `npm run build` and host `frontend/dist` on
Amplify Hosting (or any static host). DynamoDB defaults to on-demand billing, about 1.25 USD per
million writes; a 30-day backfill is roughly 6,000 writes.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | service check |
| POST | `/telemetry` | one reading |
| POST | `/telemetry/batch` | up to 500 readings |
| GET | `/telemetry?well_id=BW-001` | latest readings (Streamlit uses this) |
| GET | `/wells` | registered wells and their latest reading |
| POST | `/wells` | register a well: bore type, depth, intake, pump flow, fractures, rainfall |
| GET | `/wells/{id}?days=45` | full analysis: forecast, findings, cycles, daily series, last 72 h |

Record format: `docs/telemetry-schema.md`.

## How well it works today (simulated data)

- The web app's simulator catches 31 of 36 scenario × bore combinations (`npm run validate`).
- The backend analysis, working only from telemetry a device would send, also catches 31 of 36.
- Misses are mostly on the hand-pump bore, where a hand stroke barely moves the water.
- Acoustic depth (simulated) is within 5 cm; transmissivity from the refill fit is within ~25%.

Everything is validated on simulated data only. See `docs/limitations.md`.

## Team

- **Simulation and forecast:** `simulator/`, `frontend/src/sim/`
- **AWS backend:** `backend/` (`app.py`, `schema.py`, `analysis.py`, `storage.py`, `template.yaml`)
- **Web app and dashboard:** `frontend/`, `dashboard/`
- **Hardware and QA:** `firmware/esp32/`, `tests/`, `docs/`

The original MVP (simulator, forecast, backend, Streamlit dashboard, firmware, tests, docs) came from
the teammate repo `omkarbachhav24-ux/borewise`; the fixes made while merging are listed in
`docs/limitations.md`.

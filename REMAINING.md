# BoreWise: what is left before submission

AWS Environment Hackathon, Delhi, 8–11 October 2026. Written 11 Oct, 01:50 IST, against the team's
**48-hour implementation plan**. **Check the exact cutoff time in the event portal first**; it overrides
everything below.

## Where we stand

| Plan requirement | Status | Notes |
|---|---|---|
| Simulator: normal, weak-monsoon, over-pumping | ✅ Done | Python (`simulator/`) and in the web app; 10 scenarios total |
| Same seed reproduces the same series | ✅ Done | Fixed seeds; a test checks Python and JS agree to 1 mm |
| Pump ON → deeper, OFF → recovers | ✅ Done | Tested |
| Configurable intake threshold per well | ✅ Done | `min_submergence_m` per well; threshold = intake − submergence; tests |
| Baseline forecast with assumptions | ✅ Done | 21-day trend, P10/P50/P90 dates, cut-to-monsoon. Assumptions are not yet shown as text in the UI |
| Risk % of crossing within **7 and 30 days** | ❌ Missing | Plan ticket S5 |
| Forecast evaluation: **MAE in days** on held-out profiles | ❌ Missing | Plan ticket S6. We report detection (31/36), not error in days |
| Validation: missing field, bad depth, bad JSON rejected | ✅ Done | `backend/schema.py`, tested |
| **Stale** timestamps flagged | ✅ Done | Late device readings stored with `stale: true`, excluded from the forecast; future device timestamps rejected |
| **Flatline** sensor flagged | 🟡 Partial | Detects a reading stuck across pump runs; no check for identical heartbeats |
| `pump_state: UNKNOWN`, `flow_lpm`, underscore `data_source` names | ✅ Done | Both spellings accepted, stored with hyphens; tests |
| Store readings in DynamoDB | ✅ Code done | Single table; latest state is computed on read instead of a `WellState` table (fine) |
| **Deployed AWS endpoint** | 🟡 **Ready to deploy** | One command: `infra/deploy.ps1`. Smoke test passes 18/18 locally. **Most important gap** |
| Budget alert, least-privilege IAM | 🟡 Files ready | `infra/deployer-policy.json`, budget created by the deploy script |
| Dashboard showing trend, threshold, forecast, action | ✅ Done | React 3D app and Streamlit |
| Dashboard reads the **deployed** AWS API | ❌ Blocked by deploy | Works against the local API; verified end to end |
| Cycle diagnostics and quality flags | ✅ Done | Recovery fit, findings, sensor-fault flag |
| ESP32: DS18B20, pump-state input | ❓ Unknown | Firmware written, **not compiled or flashed**. Team to confirm |
| Short PVC tube acoustic trial | ❓ Unknown / likely not done | Optional. Report honestly if skipped |
| Public repo with setup instructions | 🟡 Check | README done. Code is on `omkar281006/bore-well-`; make sure the repo is **public** |
| `SUBMISSION.md` write-up | ❌ Missing | Plan section 7 outline |
| Demo video, 3 min or less | ❌ Missing | Needs the deployed AWS round trip on screen |
| `config/` well profiles | ✅ Done | `config/wells.json`: 3 wells; `fleet --config` registers them |
| Links work while signed out; portal form submitted; receipt saved | ❌ Pending | Last step |

## Do these in order

Times assume the team works in parallel. Stop optional work if step 1 slips.

### 1. Deploy to AWS (Person 2, about 30 min). Blocks the video

Follow **`infra/README.md`**: create the scoped `borewise-deployer` IAM user, then

```powershell
cd D:\borewise
$env:AWS_PROFILE = "borewise"
powershell -ExecutionPolicy Bypass -File infra\deploy.ps1 -Email you@example.com
```

It creates the budget alert, deploys, writes `frontend/.env`, loads the 3 wells from `config/wells.json`
and writes `docs/deployment-evidence.md`. Done when that file says 18 of 18 against the AWS URL.

### 2. Point the dashboards at AWS (Person 3, 15 min)

- `frontend/.env`: `VITE_API_URL=<ApiUrl>`, then `npm run dev`, switch to **Live API**.
- Streamlit: API mode, URL `<ApiUrl>/telemetry`, then Fetch.
- Optional but strong: `npm run build`, then host `frontend/dist` on **Amplify Hosting** (drag-and-drop
  deploy) for a public URL judges can open.

### 3. Close the plan's code gaps (Person 1, about 2 h)

| Gap | Where | Done when |
|---|---|---|
| ~~`min_submergence_m`, stale flag, plan schema names, `config/wells.json`~~ | done | 10 new tests, 35/35 pass |
| 7-day and 30-day crossing risk (%) | `backend/analysis.py` forecast: Monte Carlo over trend uncertainty | Values between 0 and 100; shown in the UI |
| Flatline flag (8 identical valid heartbeats) | `backend/analysis.py` | Raises the sensor-fault finding |
| Show assumptions under the forecast | web app forecast card | Trend window, intake, submergence, drawdown listed |

### 4. Forecast evaluation (Person 1, about 1 h). Gives honest numbers for the write-up

Script `tests/evaluate_forecast.py`:
- For each scenario and bore, run the season, record the true day the level first reaches the threshold.
- Make forecasts at several points before that, using only data up to that point.
- Report **MAE in days**, misses, false warnings on healthy wells, and P10–P90 coverage.

### 5. Hardware status (Person 4, time-box to 1 h)

- Compile and flash `firmware/esp32/main.cpp`; send one real reading to the AWS endpoint
  (`data_source: bench-tested` only if a real sensor produced it).
- If a DS18B20 or switch is available, show it working. If not, document it and move on.
- Skip the acoustic tube unless everything else is done.

### 6. Write-up `SUBMISSION.md` (Person 4, about 45 min)

Follow the plan outline: problem and users, solution, build, AWS usage (name the resources: API Gateway,
Lambda, DynamoDB, CloudWatch, SAM, Amplify), evaluation (only tests actually run), limitations
(simulated vs bench vs field), next step (field calibration against a dipper reading).
Reuse numbers from `README.md` sections 10 and 15.

### 7. Demo video, 3 min or less (whole team, about 1.5 h including retakes)

| Time | Show |
|---|---|
| 0:00–0:25 | The problem: a Pune society, a tanker bill, a burnt pump |
| 0:25–0:55 | Web app: the well, depth to water, the intake threshold |
| 0:55–1:35 | Switch normal → weak monsoon → over-pumping; the forecast and advice change |
| 1:35–2:10 | **Send a reading to the deployed AWS API** (fleet or Streamlit dispatcher); it appears in the app. Show the Lambda and DynamoDB items in the AWS console |
| 2:10–2:35 | Inject a bad or flatline reading; it is rejected or flagged, with no false alarm |
| 2:35–3:00 | What is simulated, what hardware was tested, what is not verified yet; next step is a field pilot |

Upload as **unlisted** (YouTube) or public (Drive with "anyone with the link").

### 8. Submit (about 30 min, aim for at least 2 h before the cutoff)

- [ ] Repo public; README renders; setup works from a clean clone
- [ ] Video plays in a private/incognito window
- [ ] AWS endpoint and web app URL respond in incognito
- [ ] Portal form filled; screenshot of the confirmation saved
- [ ] After submitting, **no new features**. Fix only real blockers

## Do not do now

- Deep-borewell acoustic ranging, IoT Core / MQTT, OTA updates, pump switching, XGBoost or other ML.
- New 3D or UI features. The web app is already the strongest part of the demo.
- Claims of real-world accuracy. Every number we have comes from simulation.

## Last-12-hours rule (from the plan)

No new features unless a required deliverable is blocked. A reliable demo, honest evidence, setup
instructions and a successful submission matter more than extra complexity.

# BoreWise: full context for a blog post

Everything a writer needs to tell the BoreWise story without opening the code: the problem, how the idea changed,
the physics, what was built, the hard bugs, results, honest limits, and ready-made angles, titles and quotes.

> **Fill before publishing:** the four `[brackets]` in the Quick facts table, the team names, and whether the
> AWS deploy and video were completed. Do not claim anything that did not happen. All results so far come from
> simulation.

---

## Quick facts

| | |
|---|---|
| Project | **BoreWise**: an acoustic borewell monitor that forecasts the day a well runs dry and explains why |
| Event | AWS Environment Hackathon, Delhi, 8–11 October 2026 |
| Track | Heat and Water (groundwater and droughts) |
| Team | VIT Pune students `[names and roles]` |
| Repository | https://github.com/omkar281006/bore-well- |
| Live API | `[https://….execute-api.ap-south-1.amazonaws.com, or "not deployed"]` |
| Demo video | `[link]` |
| Interactive prototype | https://claude.ai/artifact/BB2WkT7Fw6W38TMQMf7d38 `[check it is shared publicly before linking]` |
| Stack | React 18 + Three.js, Python, AWS SAM, API Gateway, Lambda, DynamoDB, CloudWatch, ESP32 firmware, Streamlit |
| Status | Software complete and tested on simulated data; hardware designed, not built |

**One-line pitch:** Every pump cycle is a free aquifer test. BoreWise listens to the water, reads the refill,
and tells a housing society the day its borewell will run dry, why, and how much to cut pumping to last
until the monsoon.

---

## 1. The problem

Pune housing societies and farm co-operatives pump their borewells blind. They discover a failing well when
the pump starts sucking air. By then:

- the motor may have burnt out running dry (a 1–3 HP submersible costs about ₹7,000–19,300),
- the society is buying private tankers for the rest of the summer,
- and nobody knows whether the cause is the aquifer, the well, the pump or the neighbours.

**Why Pune's wells fail fast.** Most bores are drilled into Deccan basalt: stacked lava flows where water sits
in thin vesicular layers and fractures. The deep aquifer stores very little water and sustains pumping for
only **0.5–3 hours** before the level collapses (CGWB aquifer mapping, Pune). When the water table drops below a
water-bearing fracture, the yield can fall suddenly rather than gradually.

**Numbers that set the scene**

| Fact | Number | Source |
|---|---|---|
| Pune talukas below their 5-year May water level (May 2026) | 11 of 13 | [Pune Pulse](https://www.mypunepulse.com/?p=205378) |
| Private tanker price, Pune | ~₹1,000 rising to ~₹2,000 a load by June 2026 | [The Bridge Chronicle](https://www.thebridgechronicle.com/pune/pune-water-crisis-tanker-costs-housing-society-maintenance-bills-rise-agn97) |
| One society's tanker bill (Sun Exotica, Yewalewadi, Mar–Jun) | ~₹7.5 lakh, ~100 tankers a month | same |
| PMC tanker trips a year | 3.07 lakh (2021-22) → 4.00 lakh (2023-24) → ~4.9 lakh (2024-25) | [Punekar News](https://punekarnews.in/pune-struggles-with-water-scarcity-150-160-tankers-deployed-daily-to-meet-demand-4-03-lakh-rounds-of-tankers-recorded-in-last-fiscal), [FPJ](https://www.freepressjournal.in/amp/pune/residents-staged-a-protest-against-tanker-mafia-demand-permanent-water-supply-in-south-pune) |
| Atal Bhujal working metered wells vs target | 3,892 vs 50,000 | [World Bank P158119](https://projects.worldbank.org/P158119?lang=en) |
| India groundwater use | ~247 BCM/yr, 60.6% of extractable; 730 of 6,762 units over-exploited | GWRA 2025 (see `docs/research-report.md`) |
| Imported sonic water-level meters | US$1,675–2,915 | [Fondriest / Eno](https://fondriest.com/eno-scientific-well-watch-700-water-level-monitor.htm) |
| Farm proxy (Karnataka, 1,500 farmers) | over 60% had a well dry up; ~₹50,000 per failed bore | [IDR summary](https://idronline.org/can-indian-farmers-adapt-to-water-loss/) |
| Payback (computed) | avoiding one tanker a week ≈ ₹78k–1.04 lakh a year, vs a ₹2–2.5k device | our calculation |

**Who it is for:** society secretaries and facility managers, farm co-operatives, and ward or taluka officers
who plan tanker supply.

---

## 2. How the idea evolved (good material for a "journey" section)

The first pitch was a "Thermo-Acoustic Borewell Yield Predictor": drop an ESP32 down the shaft, stream to
AWS IoT Core and Timestream, model it on SageMaker, and use NASA GRACE-FO satellite data. A critique round
changed almost every part:

| First idea | What changed | Why |
|---|---|---|
| Sensor lowered down the shaft | Sensor stays **at the wellhead**, sounding down a 25 mm PVC tube | A working borewell is packed with pump, riser and cable; nobody risks a ₹50k pump for a sensor |
| Ultrasonic module | **Acoustic echo sounding** with low-frequency chirps | Water is 30–150 m down; a JSN-SR04T reaches about 4.5 m |
| Temperature as a predictor | Temperature is for **speed-of-sound correction** | About 0.17% depth error per °C |
| GRACE-FO as the main input | Regional context only | Monthly and about 300 km per pixel; useless for one well |
| Amazon Timestream | Dropped for DynamoDB | Closed to new AWS customers since June 2025 |
| "Predict yield" | **Treat every pump cycle as an aquifer test** | Turns a level gauge into a diagnostic tool |
| Build real hardware first | **Simulate the hardware first**, physics-based | Removes the riskiest part; lets us test many failure types |
| Demo only | Inject 9 failure types into simulated wells and score detection | Evidence, not just a pretty demo |
| Long name | **BoreWise** | Easier to remember |

---

## 3. The core insight

Acoustic sounding is not new: oilfield "echometers" have done it for decades. What nobody does is **read the
pump cycles a society already runs every day**.

When the pump stops, the water climbs back. How it climbs is a free pump test:

- the **Theis recovery** slope gives the aquifer's **transmissivity** (how easily water flows in),
- the drop at switch-off gives the **specific capacity** and the **well loss** (clogging),
- the motor current gives the **pump's health**,
- the settled level before each run, day after day, gives the **seasonal decline**.

Tracking these over weeks separates problems that look identical from the surface ("the water is low"):

| Problem | Water table | Refill slope | Drawdown per run | Motor current | Right action |
|---|---|---|---|---|---|
| Seasonal depletion | falling | steady | steady | steady | Ration until the monsoon |
| Fracture dewatered | falls past a fracture | **drops sharply** | grows | steady | Shorter, spaced-out runs |
| Well clogging | steady | steady | **grows** | steady | Clean the well; rationing won't help |
| Pump wear | steady | steady | **shrinks** | **drops** | Service the pump |
| Neighbour interference | **falls while our pump is off** | — | — | — | Agree pumping times |
| Dry running | at the intake | — | — | **drops** | Stop the pump now |
| Sensor fault | reading stuck | — | **near zero** | normal | Check the sounding tube |

This table is the heart of the blog: same symptom, seven causes, seven different fixes.

---

## 4. How it works, step by step

1. **Chirp.** A 60–250 Hz logarithmic chirp goes down a 25 mm sounding tube. Low tones survive the ~150 m
   round trip; kHz tones die in a narrow tube (about 61 dB loss at 100 Hz vs 193 dB at 1 kHz over 150 m).
2. **Echo.** Cross-correlation (matched filtering) finds the echo off the water surface. A time-varying gain,
   capped at 46 dB, undoes tube loss; parabolic interpolation refines the peak.
   Depth = c·τ/2, with c = (331.3 + 0.606·T) × (1 − 0.0082) for air temperature and tube width.
   Readings are taken only while the pump is off (pump noise ruins the echo).
3. **Refill.** After each run, a reading every 2 minutes for an hour. Points 45+ minutes after switch-off are
   fitted on a Theis recovery plot (residual drawdown vs log₁₀ t/t′); T = 2.303·Q / (4π·slope).
4. **Forecast.** A 21-day trend of the pre-pump water table, plus typical drawdown, is compared with the
   pump's safe threshold (**intake depth minus minimum submergence**, 2 m by default). Output: P10/P50/P90
   dry-up dates and the pumping cut that carries the well to the monsoon (about 10 June).
5. **Diagnose and alert.** Findings are ranked by severity and written as WhatsApp-style alerts in
   **English, Marathi and Hindi**.

**Hardware (designed, ~₹2,000–2,500):** ESP32, I2S MEMS microphone (INMP441), I2S amplifier (MAX98357A) and a
small speaker at the top of the tube, DS18B20 temperature sensor, SCT-013 clip-on current clamp for pump state,
Wi-Fi upload.

**Device protocol:** a heartbeat every 15 minutes, an event whenever the pump switches, and a reading every
2 minutes for the first hour after switch-off.

---

## 5. What we built

### Web app (the face of the project)
React 18 + Three.js, one animation loop.

- **3D cutaway of a Deccan-basalt borewell:** lava-flow layers (vesicular basalt, red bole, massive basalt), the
  water table with a live cone of depression, fractures that glow when water-bearing and go grey when
  dewatered, a society building, monsoon rain, a depth ruler.
- **Four realistic bore types:** open-hole borewell, screened tubewell (PVC, slotted screens, gravel pack),
  dug-cum-bore well, and an India Mark II hand pump with an animated handle. Close up, every part is labelled:
  submersible motor, impeller stages, non-return valve, riser, starter panel with dry-run lamp, the BoreWise unit.
- **Nine failure scenarios** you can switch between live.
- **Panels:** depth, dry-up forecast with a P10–P90 timeline and one-click rationing, diagnosis, season chart,
  last 72 hours, the recovery fit, the acoustic echo with the maths shown, a ward "groundwater radar" of 36
  society wells, alert preview in three languages.
- **Polish:** sonar intro and camera dive, bloom-lit water, sound (the real chirp pitched up so laptops can play
  it), light and dark mode, reduced-motion support, phone layout.
- **Demo / Live API switch:** demo runs the simulator in the browser; live reads the real backend.
  `?well=BW-003` in the address bar picks a well.

### Physics simulator
The same model in JavaScript (browser) and Python (backend tests and fleet); a test checks they agree to 1 mm.
Cooper–Jacob drawdown with wellbore storage, superposition over pump runs, well loss and skin (clogging),
fracture-controlled transmissivity, seasonal decline, monsoon recharge from synthetic Pune rainfall,
neighbour interference, pump wear. 10 scenarios × 4 bore types.

### Backend
One Python router that runs both as an AWS Lambda and as a local server.

- **Validation (schema v2):** missing fields, impossible depths, timestamps without a timezone, bad enums,
  device clocks in the future and malformed JSON are rejected with a reason. Late readings are stored but
  flagged `stale` and kept out of the forecast. Depth may be null while the pump runs.
- **Analysis engine:** works only from what a device sends: cycle detection, recovery fit, daily series,
  forecast, findings.
- **Storage:** one DynamoDB table (partition key `well_id`, sort key `timestamp`, well settings at `#META`).

### AWS deployment
Infrastructure as code with **AWS SAM**: API Gateway HTTP API (throttled to 20 req/s), Lambda (Python 3.12,
arm64), DynamoDB on-demand, CloudWatch logs and an error alarm. One-command deploy script, a scoped IAM policy,
a $5 budget alert, and a smoke test with 18 checks that writes its own evidence file. Cost for the hackathon:
a few cents. `[Deployed and verified 18/18 on AWS: yes / no]`

### Also built
- **Simulator fleet:** posts ESP32-style telemetry from many virtual wells to the API, with a live mode.
- **Streamlit dashboard:** engineering view with raw readings, cycle table and a test dispatcher.
- **ESP32 firmware:** NTP time, current clamp RMS, gated sounding, batching. Not compiled or flashed yet; the
  acoustic function is a stub.
- **Research report:** acoustics, hydrogeology, equations, failure signatures, data sources, costs, competitors.

---

## 6. Architecture

```
 ESP32 at the wellhead          Simulator fleet
        │  POST /telemetry/batch       │
        └──────────────┬───────────────┘
                       ▼
        API Gateway HTTP API (throttled)
                       ▼
        Lambda: validate → store → analyse
                       ▼
        DynamoDB (well_id + timestamp)
                       │
         GET /wells/{id}│                 GET /telemetry
                       ▼                         ▼
        3D web app (React + Three.js)     Streamlit dashboard
```

Why serverless: a well reports every 15 minutes, so the load is tiny and spiky. Lambda + DynamoDB on-demand
costs almost nothing at idle and needs no servers to babysit during a hackathon.

---

## 7. Results (only tests we ran)

| Check | Result |
|---|---|
| Python test suite | 36 / 36 pass |
| Web app simulator tests | 5 / 5 pass |
| API smoke test, local rehearsal | 18 / 18 pass |
| API smoke test, live on AWS | `[18 / 18, or not run]` |
| Fault detection, 4 bore types × 9 scenarios | 32 / 36 caught (27 / 27 on submersible bores) |
| Stress test, 36 wells, 400k readings | 0 server errors, 200 / 200 bad records rejected |
| Acoustic depth, simulated, 161 pings | mean bias 0.2 cm, worst 4.6 cm |
| Transmissivity from the refill fit | within about 25% of the simulator's true value |
| Python vs JavaScript physics | agree to 1 mm |
| End to end: fleet → API → analysis → web app | verified in a headless browser |

**Where it misses:** on a hand-pump bore, one stroke barely moves the water, so clogging, wear, fracture and
sensor faults are invisible; pump wear is also missed on the dug-cum-bore well. On dug-cum-bore wells the
large open section stores so much water that the refill fit cannot estimate transmissivity (the app shows "—").

---

## 8. Engineering stories (the bugs that make a blog interesting)

1. **The 3D scene that never rendered.** The first prototype showed a blank canvas in every version. Cause:
   JavaScript's "temporal dead zone": variables used inside a `try` block before their `let` declaration ran,
   so initialisation threw silently. Fix: move setup into an `init3D()` function called after declarations.
2. **The echo that read 60 cm too deep.** The simulated sounder was consistently biased by 0.5–0.7 m. Two causes:
   the peak was taken from a smoothed envelope (which shifts it), and uncapped gain amplified far-end noise until
   noise beat the real echo. Fix: cap the gain at 46 dB and snap to the raw correlation peak. Worst error fell to
   4.6 cm.
3. **A drawdown of 860 m.** An earlier simulator let drawdown run away far below the bottom of the well.
   Rebuilt on proper Cooper–Jacob physics with wellbore storage and a dry-run cut-off.
4. **A forecast that flipped every hour.** Risk jumped between Normal, Warning and High Risk because the trend
   used every reading, including pumping drawdown. Fix: trend only the pre-pump (recovered) water level.
5. **Timestamps that sorted wrong.** Readings with `+05:30` and `Z` offsets sorted as text, not time. Fix:
   normalise every timestamp to UTC on ingest so DynamoDB's sort key orders correctly.
6. **False clog alarms on hand pumps.** A hand stroke barely moves the water, so tiny changes looked like
   clogging. Fix: only run clog/fracture/wear checks when drawdown is meaningful (over 2.2 m).
7. **The bug a local test could not catch.** Listing wells worked locally but would have failed on AWS: a
   DynamoDB `Scan` returns at most 1 MB per call, so with ~11,000 readings in the table the well records were
   on later pages. Fix: page through the whole table; a test fakes 1 MB pages to prove it.
8. **Late data poisoning the forecast.** A device that buffers readings offline could upload days-old data
   later. Fix: store it, flag it `stale`, and keep it out of the forecast; reject device clocks set in the future.

---

## 9. Honest limitations

- **Everything is validated on simulated data.** Field accuracy is unknown.
- The acoustic sounder is designed and simulated but **not built**. No published measurement exists of a
  low-cost mic-and-speaker setup in a tube deeper than about 100 m; that is the biggest technical risk.
- ESP32 firmware is written but not flashed `[update if it was]`.
- The weak-monsoon check needs daily rainfall per well (IMD gridded data in production).
- Marathi and Hindi alert text needs a native-speaker review.

---

## 10. What's next

1. Bench test: a 30–60 m coil of PVC pipe to measure real echo strength.
2. Dipper-calibrated pilot in 5–10 Pune society borewells and Purandar/Baramati farm bores: compare BoreWise's
   level with a manual dipper after each pump cycle, then check the dry-date forecast against reality.
3. WhatsApp alerts and Marathi/Hindi explanations.
4. A cheaper tier using only the pump's current clamp.
5. Automatic dry-run cut-off and pump scheduling via a relay.
6. Open-data export to CGWB / Atal Jal programmes.

---

## 11. Competitors and how BoreWise differs

| Who | What they do | Gap |
|---|---|---|
| Waterlab Bhujal (app + IoT pilot) | Spot water-level estimates | No recovery analytics, forecast or diagnosis |
| WEGoT | Apartment water consumption meters | Measures use, not the aquifer |
| FluxGen | Industrial water IoT | Not borewell forecasting |
| GSM pump starters, KirloSmart | Remote start/stop, react to dry run | React after the damage starts |
| Government DWLR piezometers | Accurate level in dedicated wells | Needs a non-pumped well; not for societies |
| Imported sonic meters (Eno, Solinst) | ±3 cm acoustic ranging | 50–100× the price; no analytics |

---

## 12. Blog angles and titles

**Possible angles**
- *Problem-first:* the hidden cost of borewells failing silently in Pune, and a ₹2,000 fix.
- *Insight-first:* "Every pump cycle is a free aquifer test", the idea that turns a level gauge into a doctor.
- *Build log:* 4 days, one hackathon: from an over-ambitious pitch to a working, tested system.
- *Engineering deep dive:* echo sounding 150 m down a 25 mm pipe, plus the bugs we hit.
- *AWS-focused:* a serverless IoT backend for a few cents with SAM, Lambda and DynamoDB.

**Title ideas**
- Every Pump Cycle Is an Aquifer Test
- Listening to Borewells: Forecasting the Day a Well Runs Dry
- BoreWise: A ₹2,000 Answer to Pune's Tanker Summers
- How We Turned a Water-Level Gauge into a Groundwater Doctor
- Echoes in a Pipe: Building BoreWise at the AWS Environment Hackathon

**Suggested structure (1,500–2,000 words)**
1. Hook: a society discovers its well is dry when the pump burns out (sections 1)
2. Why basalt wells fail fast (1)
3. The pivot: from a probe down the shaft to listening from the top (2)
4. The insight and the diagnosis table (3)
5. How it works in five steps (4), with one diagram
6. What we built, with screenshots of the 3D app (5, 6)
7. Bugs we learned from: pick 2–3 (8)
8. Results and honest limits (7, 9)
9. What's next and how to try it (10, repo link)

**Pull quotes**
- "The sensor isn't the new part. Reading the pump cycles a society already runs every day is."
- "Same symptom, seven causes, seven different fixes."
- "Rationing won't save a clogged well, and cleaning won't save a depleted aquifer."
- "Every number here comes from simulation. The next number we want is a dipper reading in a real well."

**Screenshots to capture**
- The 3D cutaway in dark mode, overview camera, over-pumping scenario with "Dry in N days"
- The same well in light mode
- The recovery-fit chart and the echo chart
- The four bore types side by side
- The ward groundwater radar
- Live API mode showing BW-003 "Level drops while your pump is off"
- The AWS console: CloudFormation stack, DynamoDB items `[if deployed]`

---

## 13. Glossary (for non-specialist readers)

| Term | Plain meaning |
|---|---|
| Borewell | A narrow, deep well drilled into rock, with a submersible pump at the bottom |
| Water table / static water level | Depth to water when the pump has been off long enough to recover |
| Drawdown | How far the water drops while pumping |
| Pump intake | The depth of the pump's inlet; water must stay above it |
| Minimum submergence | Extra water the pump needs above its intake to avoid sucking air |
| Transmissivity (T) | How easily water flows through the rock to the well (m²/day) |
| Specific capacity | Litres per minute pumped per metre of drawdown; a health score for the well |
| Theis recovery | A classic method to read T from how the water level recovers after pumping stops |
| Cone of depression | The dip in the water table around a pumping well |
| Deccan basalt | Layered volcanic rock under Pune; holds water only in thin layers and fractures |
| Matched filtering | Finding a known signal (the chirp) in noise by correlating against it |
| P10 / P50 / P90 | Pessimistic, central and optimistic estimates of the dry-up date |

---

## 14. Links

- Repository: https://github.com/omkar281006/bore-well-
- Full README: `README.md`; submission write-up: `SUBMISSION.md`
- Research report with all sources: `docs/research-report.md`
- Architecture: `docs/architecture.md`; telemetry format: `docs/telemetry-schema.md`
- Limitations: `docs/limitations.md`; deploy guide: `infra/README.md`

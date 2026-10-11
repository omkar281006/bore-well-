# Demo video script (≤ 3:00)

Record at 1080p. Before recording: deploy done, `frontend/.env` points at AWS, `npm run dev` running,
the three wells loaded (`config/wells.json`), AWS console open in a second tab (Lambda + DynamoDB),
a PowerShell window in `D:\borewise` with `$api` set.

| Time | Screen | Say (roughly) |
|---|---|---|
| 0:00–0:25 | A photo or the 3D app's intro | "In Pune, housing societies find out their borewell is failing when the pump starts sucking air. By then the motor has burnt and they're paying ₹2,000 a tanker. Basalt wells here sustain pumping for only half an hour to three hours." |
| 0:25–0:55 | Web app, Demo mode, Overview → Water table camera | "BoreWise turns every pump cycle into an aquifer test. A ₹2,000 sounder at the wellhead measures depth to water. Here's the water table, the pump intake, and the safe threshold above it." |
| 0:55–1:35 | Switch scenarios: Healthy → Weak monsoon → Over-pumping | "Healthy well: safe till the monsoon. Weak monsoon: the decline steepens. Over-pumping: it now says dry in N days, and how much to cut pumping to reach 10 June. It also tells you *why*: depletion, clogging, a dewatered fracture, pump wear or a neighbour." |
| 1:35–2:10 | Header → **Live API**, `?well=BW-001`; run `python -m simulator.fleet --api $api --scenario overpump --well-id BW-001 --days 1 --live`; cut to the AWS console: Lambda invocations, DynamoDB items | "This is live on AWS: API Gateway, Lambda and DynamoDB, deployed with SAM. A reading posted now appears in the app within seconds. Here are the items in DynamoDB." |
| 2:10–2:35 | PowerShell: post a bad reading (depth 999 m) → 400; show `docs/deployment-evidence.md` (18/18) | "Bad data is rejected with a reason; late readings are stored but kept out of the forecast. Our smoke test passes 18 of 18 against the live API." |
| 2:35–3:00 | `?well=BW-003`, then the limitations table in `SUBMISSION.md` | "A neighbour's pumping shows up as a level drop while our pump is off. Everything you saw runs on simulated data; next we pilot it against manual dipper readings in Pune society wells." |

Bad-reading command for 2:10:

```powershell
curl.exe -X POST "$api/telemetry" -H "Content-Type: application/json" -d '{\"well_id\":\"BW-001\",\"timestamp\":\"2026-10-11T10:00:00Z\",\"data_source\":\"simulated\",\"depth_to_water_m\":999,\"temperature_c\":28,\"pump_state\":\"OFF\",\"pump_run_minutes\":0,\"measurement_valid\":true}'
```

Upload as **unlisted** on YouTube (or Drive, "anyone with the link"), then open the link in an incognito window to check.

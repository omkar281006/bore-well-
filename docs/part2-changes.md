# Part 2 change summary (for review before merging)

## Files

| File | Change |
|---|---|
| `backend/schema.py` | `pump_state: UNKNOWN`; optional `flow_lpm` (0–5000); `bench_tested` / `field_measured` accepted and stored with hyphens; device timestamps > 10 min in the future rejected; `received_at` and `stale` added on ingest; `min_submergence_m` validated; `threshold_depth()` |
| `backend/analysis.py` | stale and `UNKNOWN` readings excluded from cycles and forecast (counted in `excluded_readings`); threshold = `intake_m − min_submergence_m`; response adds `threshold_m`, `data_quality` |
| `backend/app.py` | responses report `stale` (single) and stale count (batch) |
| `backend/storage.py` | **bug fix**: `GET /wells` on DynamoDB now pages through the whole table (it used to read only the first 1 MB, so wells could go missing once readings piled up) |
| `backend/template.yaml` | `StaleAfterHours` parameter; API throttled to 20 req/s, burst 50; Lambda logs kept 14 days; `FunctionName` output |
| `backend/samconfig.toml` | new: non-interactive deploy settings (stack `borewise`, `ap-south-1`) |
| `simulator/fleet.py` | `--config config/wells.json` registers and backfills each profile |
| `config/wells.json` | new: BW-001 over-pumping (open), BW-002 healthy (screened), BW-003 neighbour interference (dug-cum-bore) |
| `infra/*` | new: deploy guide, `deploy.ps1`, scoped IAM policy, 5 USD budget definition |
| `scripts/smoke_test.py` | new: 18 checks against any API URL, writes `docs/deployment-evidence.md` |
| `frontend/src/api/client.js` | `?well=BW-00x` in the URL picks the live well |
| `frontend/src/components/{Header,Stage,Dashboard}.jsx` | show "—" instead of "NaN" when transmissivity cannot be fitted (dug-cum-bore wells) |
| `tests/*` | 11 new tests (36 total) |
| `.gitignore` | also ignores `.env.*` (except `.env.example`), `.aws/`, `credentials`, `*.pem` |

## What `infra/deploy.ps1` creates in your AWS account

| Resource | Name | Cost for the hackathon |
|---|---|---|
| AWS Budget | `borewise-hackathon`, 5 USD/month, email at 20%, 80%, forecast 100% | free (first 2 budgets) |
| S3 bucket + its stack | `aws-sam-cli-managed-default-samclisourcebucket-…` (SAM uploads the code zip here) | cents |
| CloudFormation stack | `borewise` | free |
| DynamoDB table | `borewise-telemetry` (on-demand, PK `well_id`, SK `timestamp`) | ~12,000 writes for the 3 wells ≈ 0.02 USD |
| Lambda function | `borewise-ApiFunction-…` (Python 3.12, arm64, 512 MB, 20 s) | free tier |
| IAM role | `borewise-ApiFunctionRole-…` (read/write on that one table, X-Ray, logs) | free |
| API Gateway HTTP API | `$default` stage, CORS, throttled | free tier |
| CloudWatch | log group (14 days), alarm on ≥ 5 Lambda errors in 5 min | free tier |

It also writes `frontend/.env` (git-ignored) and `docs/deployment-evidence.md`.
Remove everything afterwards with `sam delete --stack-name borewise --region ap-south-1` (the budget stays until you delete it).

## Tests

- Python: 36 / 36 (`python -m pytest tests`)
- JavaScript physics: 5 / 5 (`cd frontend && npm test`)
- Smoke test against the local API: 18 / 18 (`docs/local-rehearsal-evidence.md`)
- Live mode in a browser, local API, all three wells loaded: correct well, findings shown, no NaN

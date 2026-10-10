# Deploying BoreWise to AWS (Part 2, items 1–3)

About 30 minutes the first time. Everything runs from your laptop with your own AWS account.
Region `ap-south-1` (Mumbai), stack `borewise`. Expected cost for the hackathon: well under 1 USD.

## 0. Install once

- AWS CLI v2 and AWS SAM CLI (Windows installers from the AWS docs)
- Python 3.10+ (already used for the simulator)

Check: `aws --version`, `sam --version`, `python --version`.

## 1. Budget alert and a scoped IAM identity (do this before deploying)

**Do not deploy with the root account or root access keys.**

1. Sign in to the console as the account owner, open **IAM → Policies → Create policy → JSON**, paste
   `infra/deployer-policy.json`, and name it `BoreWiseDeployer`.
   It only allows the stack `borewise*`, the SAM artifact bucket, Lambda/DynamoDB/IAM roles named `borewise-*`,
   HTTP APIs, logs, alarms and budgets.
2. **IAM → Users → Create user** `borewise-deployer`, attach only `BoreWiseDeployer`.
   Open the user → **Security credentials → Create access key → Command Line Interface**. Copy both keys.
3. On your laptop:
   ```powershell
   aws configure --profile borewise      # paste the keys, region ap-south-1, output json
   $env:AWS_PROFILE = "borewise"
   aws sts get-caller-identity           # must show ...:user/borewise-deployer, not :root
   ```
4. The budget (5 USD/month, emails at 20%, 80% and forecast 100%) is created by the deploy script below.
   To do it by hand instead: **Billing → Budgets → Create budget → Monthly cost budget, 5 USD, your email**.
   Note: Budgets can need the owner to enable *IAM user access to billing* (Account settings). If the script
   says AccessDenied on budgets, create the budget in the console as the owner, then rerun.

## 2. Deploy and verify `/health`

```powershell
cd D:\borewise
$env:AWS_PROFILE = "borewise"
powershell -ExecutionPolicy Bypass -File infra\deploy.ps1 -Email you@example.com
```

The script refuses to run as root, creates the budget if missing (or use `-SkipBudget` if you made it in the
console), runs `sam deploy` (settings in `backend/samconfig.toml`), writes the `ApiUrl` into `frontend/.env`,
then runs the smoke test. There is no `sam build` step: the Lambda has no third-party packages (boto3 is in the
Lambda runtime), so your laptop's Python version does not need to be 3.12.

Manual equivalent:

```powershell
cd D:\borewise\backend
sam deploy --template-file template.yaml   # samconfig.toml: stack borewise, ap-south-1, no prompts
aws cloudformation describe-stacks --stack-name borewise --query "Stacks[0].Outputs" --output table
curl.exe https://<id>.execute-api.ap-south-1.amazonaws.com/health
```

`/health` must say `"store": "dynamodb"`. If it says `memory`, the Lambda did not get `DYNAMODB_TABLE`.

If `sam deploy` stops with **AccessDenied**, the error names the missing action: add it to
`BoreWiseDeployer` (keep it scoped to `borewise*`) and rerun. Nothing partial is left behind;
CloudFormation rolls back.

## 3. Send simulated telemetry and verify analysis (documented evidence)

```powershell
cd D:\borewise
python scripts\smoke_test.py --api https://<id>.execute-api.ap-south-1.amazonaws.com
```

18 checks: health, valid records (including the plan's `bench_tested` / `UNKNOWN` / `flow_lpm` form),
7 kinds of invalid record rejected with 400, a late reading stored with `stale: true`, a mixed batch (207),
read-back from DynamoDB, the three wells in `config/wells.json` registered and backfilled, and
`GET /wells/BW-00x` returning a forecast, threshold and findings.

The result is written to **`docs/deployment-evidence.md`**. Commit it. A local rehearsal of the same
script (in-memory store, not AWS) is in `docs/local-rehearsal-evidence.md`: 18/18.

Then point the web app at AWS: `frontend/.env` is already written by the deploy script;
restart `npm run dev` and switch the header to **Live API**. Pick a well with the address bar:
`http://localhost:5173/?well=BW-001` (over-pumping), `?well=BW-002` (healthy), `?well=BW-003` (neighbour interference).
Streamlit: data mode **AWS Endpoint / Local API**, URL `<ApiUrl>/telemetry`, well id `BW-001`, Fetch.

If a request fails: `sam logs --stack-name borewise --region ap-south-1 --tail`, or CloudWatch → Log groups →
`/aws/lambda/borewise-ApiFunction-...`.

## Tear down after judging

```powershell
sam delete --stack-name borewise --region ap-south-1
```

This deletes the API, Lambda and table (and all telemetry).

<#
  BoreWise: one-command AWS deploy for the hackathon (Windows PowerShell).

  Run from the project root (D:\borewise):
      powershell -ExecutionPolicy Bypass -File infra\deploy.ps1 -Email you@example.com

  What it does, in order:
    1. Refuses to run as the root account (use the scoped 'borewise-deployer' IAM user)
    2. Creates the 5 USD monthly budget alert if it does not exist yet
    3. sam deploy (stack 'borewise', ap-south-1). The Lambda has no third-party packages, so no 'sam build'
       is needed, and your local Python version does not have to match the Lambda's 3.12
    4. Reads the ApiUrl output, writes frontend\.env
    5. Runs scripts\smoke_test.py against the deployed API -> docs\deployment-evidence.md
#>
param(
  [Parameter(Mandatory = $true)][string]$Email,
  [string]$Region = "ap-south-1",
  [string]$Stack = "borewise",
  [switch]$SkipSmoke,
  [switch]$SkipBudget   # use if you created the budget yourself in the console
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd not found. $hint" }
}
Need aws    "Install AWS CLI v2: https://aws.amazon.com/cli/"
Need sam    "Install AWS SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
Need python "Install Python 3.10+"

# Native tools write progress to stderr; never let that abort the script. Exit codes are checked instead.
$ErrorActionPreference = "Continue"

# 1. identity
$idJson = aws sts get-caller-identity --output json
if ($LASTEXITCODE) { throw "No working AWS credentials. Run: aws configure --profile borewise, then `$env:AWS_PROFILE='borewise'" }
$id = $idJson | Out-String | ConvertFrom-Json
if ($id.Arn -match ":root$") { throw "You are signed in as the ROOT account. Create the borewise-deployer IAM user (infra\README.md) and 'aws configure' with its keys." }
Write-Host "Deploying as $($id.Arn) (account $($id.Account))" -ForegroundColor Cyan

# 2. budget alert
if ($SkipBudget) {
  Write-Host "Skipping budget creation (-SkipBudget). Make sure a budget alert exists in Billing -> Budgets." -ForegroundColor Yellow
} else {
 # describe-budget (singular) fails with NotFound when it does not exist yet; that is expected
 aws budgets describe-budget --account-id $id.Account --budget-name borewise-hackathon --output text *> $null
 if ($LASTEXITCODE -eq 0) {
  Write-Host "Budget alert already exists" -ForegroundColor Green
 } else {
  $notes = (Get-Content "$root\infra\budget-notifications.template.json" -Raw).Replace("YOUR_EMAIL", $Email)
  $tmp = Join-Path $env:TEMP "borewise-budget-notes.json"
  Set-Content -Path $tmp -Value $notes -Encoding ascii
  aws budgets create-budget --account-id $id.Account --budget "file://$root/infra/budget.json" --notifications-with-subscribers "file://$tmp"
  if ($LASTEXITCODE) { throw "Could not create the budget. Create it in the console (Billing -> Budgets, 5 USD monthly) as the account owner, then rerun with -SkipBudget" }
  Write-Host "Budget alert created: 5 USD/month, emails to $Email at 20%, 80% and forecast 100%" -ForegroundColor Green
 }
}

# 3. deploy (packages backend\ straight from template.yaml; settings in backend\samconfig.toml)
Push-Location "$root\backend"
try {
  if (Test-Path .aws-sam) { Remove-Item -Recurse -Force .aws-sam }   # never deploy a stale build
  sam deploy --template-file template.yaml --stack-name $Stack --region $Region
  if ($LASTEXITCODE) { throw "sam deploy failed (an AccessDenied error names the IAM action to add to infra\deployer-policy.json)" }
} finally { Pop-Location }

# 4. outputs
$api = aws cloudformation describe-stacks --stack-name $Stack --region $Region --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text
if (-not $api) { throw "Stack has no ApiUrl output" }
Write-Host "ApiUrl: $api" -ForegroundColor Green
Set-Content -Path "$root\frontend\.env" -Value "VITE_API_URL=$api`nVITE_WELL_ID=BW-001" -Encoding ascii
Write-Host "Wrote frontend\.env (restart 'npm run dev', then switch to Live API)"

# 5. evidence
if (-not $SkipSmoke) {
  Push-Location $root
  try {
    python scripts\smoke_test.py --api $api --stack $Stack --region $Region
    if ($LASTEXITCODE) { Write-Host "Some smoke checks failed: see docs\deployment-evidence.md and CloudWatch logs (sam logs --stack-name $Stack --tail)" -ForegroundColor Red; exit 1 }
  } finally { Pop-Location }
}
Write-Host "Done. API: $api" -ForegroundColor Green

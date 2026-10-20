# Pantry Vision deploy (pwsh 7). Steps are idempotent; values come from the gitignored .env and are never printed.
param(
    [ValidateSet("check", "setup", "secrets", "model", "build", "deploy", "webhook", "scheduler", "budget", "all")]
    [string]$Step = "all"
)

$ErrorActionPreference = "Stop"
# gcloud prints progress and NOT_FOUND to stderr; only exit codes decide failure here.
$PSNativeCommandUseErrorActionPreference = $false
$Sdk = "C:\Users\User\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin"
if ((Test-Path $Sdk) -and ($env:PATH -notlike "*$Sdk*")) { $env:PATH = "$Sdk;$env:PATH" }

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Read-Dotenv {
    $found = @{}
    $path = Join-Path $Root ".env"
    if (-not (Test-Path -LiteralPath $path)) { return $found }
    foreach ($line in [IO.File]::ReadAllLines($path)) {
        $key, $value = $line.Trim() -split "=", 2
        if ($null -eq $value -or $key.StartsWith("#")) { continue }
        $value = $value.Trim().Trim('"').Trim("'")
        if ($value) { $found[$key.Trim()] = $value }
    }
    return $found
}

$Dot = Read-Dotenv
$Project = $Dot["GOOGLE_CLOUD_PROJECT"]
$Region = if ($Dot["GOOGLE_CLOUD_REGION"]) { $Dot["GOOGLE_CLOUD_REGION"] } else { "europe-west1" }
$AllowedChatIds = $Dot["TELEGRAM_ALLOWED_CHAT_IDS"]
if (-not $Project) { throw "GOOGLE_CLOUD_PROJECT is missing from .env" }

$Service = "pantry-bot"
$Repo = "pantry"
$Label = "app=pantry-vision"
$RunAs = "pantry-bot@$Project.iam.gserviceaccount.com"
$BuildAs = "pantry-build@$Project.iam.gserviceaccount.com"
$SchedulerAs = "pantry-scheduler@$Project.iam.gserviceaccount.com"
$PhotoBucket = "gs://$Project-pantry-photos"
$ModelBucket = "$Project-pantry-models"
$BuildBucket = "gs://$($Project)_cloudbuild"
$SecretNames = @("PANTRY_TELEGRAM_BOT_TOKEN", "PANTRY_TELEGRAM_WEBHOOK_SECRET", "PANTRY_ANTHROPIC_API_KEY")
$ModelFiles = @("models/yolo-world-s-pantry.onnx", "models/yolo-world-s-pantry.json")
$BudgetName = "pantry-vision budget"
# The billing account is in ILS; 37 ILS is about 10 USD (constitution cap).
$BudgetAmount = "37ILS"

function Invoke-Gcloud {
    & gcloud @args
    if ($LASTEXITCODE -ne 0) { throw "gcloud $($args[0..2] -join ' ') failed" }
}

# cmd swallows gcloud's stderr so NOT_FOUND never becomes a PowerShell error record
function Test-Gcloud([string]$Command) {
    cmd /c "gcloud $Command >nul 2>&1"
    return $LASTEXITCODE -eq 0
}

function Get-ProjectNumber {
    $n = (& gcloud projects describe $Project --format "value(projectNumber)") -join ""
    if ($LASTEXITCODE -ne 0 -or -not $n) { throw "cannot read the project number" }
    return $n
}

function Get-ServiceUrl { return "https://$Service-$(Get-ProjectNumber).$Region.run.app" }

function Get-Sha { return (& git rev-parse --short=12 HEAD).Trim() }

function Get-Image { return "$Region-docker.pkg.dev/$Project/$Repo/$Service`:$(Get-Sha)" }

function New-ServiceAccount([string]$Email, [string]$Name) {
    if (-not (Test-Gcloud "iam service-accounts describe $Email --project $Project")) {
        Invoke-Gcloud iam service-accounts create ($Email -split "@")[0] --project $Project --display-name $Name
    }
}

function Write-TempJson([string]$Json) {
    $tmp = New-TemporaryFile
    [IO.File]::WriteAllText($tmp, $Json)
    return $tmp
}

function Step-Check {
    if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) { throw "gcloud is not on PATH" }
    $account = & gcloud auth list --filter "status:ACTIVE" --format "value(account)"
    if (-not $account) { throw "no active gcloud account: run gcloud auth login" }
    if (& git status --porcelain) { throw "working tree is not clean: commit first (constitution: deploy committed code)" }
    & git fetch -q origin
    $ahead = (& git rev-list --count "origin/main..HEAD").Trim()
    if ($ahead -ne "0") { throw "HEAD is not pushed: push first (constitution: deployed revision maps to a pushed sha)" }
    foreach ($f in $ModelFiles) { if (-not (Test-Path $f)) { throw "missing ${f}, run training/export_onnx.py" } }
    $ids = @($AllowedChatIds -split "," | Where-Object { $_.Trim() }).Count
    if ($ids -eq 0) { throw "TELEGRAM_ALLOWED_CHAT_IDS is empty in .env" }
    Write-Host "Region $Region, sha $(Get-Sha), allow-list $ids chat id(s). Checks passed."
}

function Step-Setup {
    Invoke-Gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com `
        secretmanager.googleapis.com firestore.googleapis.com cloudscheduler.googleapis.com `
        billingbudgets.googleapis.com storage.googleapis.com --project $Project

    New-ServiceAccount $RunAs "pantry bot runtime"
    New-ServiceAccount $BuildAs "pantry Cloud Build"
    New-ServiceAccount $SchedulerAs "pantry morning scheduler"
    Invoke-Gcloud projects add-iam-policy-binding $Project --member "serviceAccount:$RunAs" `
        --role roles/datastore.user --condition None --quiet *> $null
    Invoke-Gcloud projects add-iam-policy-binding $Project --member "serviceAccount:$BuildAs" `
        --role roles/logging.logWriter --condition None --quiet *> $null

    # Photos: private, uniform access, no public access, deleted after 30 days (FR-012).
    if (-not (Test-Gcloud "storage buckets describe $PhotoBucket --project $Project")) {
        Invoke-Gcloud storage buckets create $PhotoBucket --project $Project --location $Region `
            --uniform-bucket-level-access --public-access-prevention
    }
    $lifecycle = Write-TempJson '{"rule":[{"action":{"type":"Delete"},"condition":{"age":30,"matchesPrefix":["photos/"]}}]}'
    try { Invoke-Gcloud storage buckets update $PhotoBucket --lifecycle-file $lifecycle --update-labels $Label }
    finally { Remove-Item $lifecycle -Force }
    Invoke-Gcloud storage buckets add-iam-policy-binding $PhotoBucket --member "serviceAccount:$RunAs" `
        --role roles/storage.objectCreator *> $null

    # Models: private bucket the build account can read; photos stay out of its reach.
    if (-not (Test-Gcloud "storage buckets describe gs://$ModelBucket --project $Project")) {
        Invoke-Gcloud storage buckets create "gs://$ModelBucket" --project $Project --location $Region `
            --uniform-bucket-level-access --public-access-prevention
    }
    Invoke-Gcloud storage buckets update "gs://$ModelBucket" --update-labels $Label
    Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$ModelBucket" --member "serviceAccount:$BuildAs" `
        --role roles/storage.objectViewer *> $null

    # Build account: source upload bucket and the image repository only.
    if (-not (Test-Gcloud "storage buckets describe $BuildBucket --project $Project")) {
        Invoke-Gcloud storage buckets create $BuildBucket --project $Project --location $Region --uniform-bucket-level-access
    }
    foreach ($role in @("roles/storage.objectViewer", "roles/storage.objectCreator")) {
        Invoke-Gcloud storage buckets add-iam-policy-binding $BuildBucket --member "serviceAccount:$BuildAs" --role $role *> $null
    }
    if (-not (Test-Gcloud "artifacts repositories describe $Repo --location $Region --project $Project")) {
        Invoke-Gcloud artifacts repositories create $Repo --repository-format docker --location $Region `
            --project $Project --labels $Label
    }
    $cleanup = Write-TempJson '[{"name":"keep-2","action":{"type":"Keep"},"mostRecentVersions":{"keepCount":2}},{"name":"delete-rest","action":{"type":"Delete"},"condition":{"tagState":"any","olderThan":"1d"}}]'
    try {
        Invoke-Gcloud artifacts repositories set-cleanup-policies $Repo --location $Region --project $Project `
            --policy $cleanup --no-dry-run *> $null
    } finally { Remove-Item $cleanup -Force }
    Invoke-Gcloud artifacts repositories add-iam-policy-binding $Repo --location $Region --project $Project `
        --member "serviceAccount:$BuildAs" --role roles/artifactregistry.writer *> $null

    # Firestore: retry-guard TTL and the latest-snapshot-per-location index.
    Invoke-Gcloud firestore fields ttls update received_at --collection-group pantry_updates --enable-ttl `
        --project $Project --quiet *> $null
    $have = & gcloud firestore indexes composite list --project $Project `
        --format "value(name)" | Where-Object { $_ -match "collectionGroups/pantry_snapshots/" }
    if (-not $have) {
        Invoke-Gcloud firestore indexes composite create --project $Project --collection-group pantry_snapshots `
            --field-config "field-path=location,order=ascending" `
            --field-config "field-path=last_photo_at,order=descending" --async
    }
    Write-Host "Setup done."
}

function Set-Secret([string]$Name, [string]$Value) {
    $tmp = New-TemporaryFile
    try {
        [IO.File]::WriteAllText($tmp, $Value)
        if (-not (Test-Gcloud "secrets describe $Name --project $Project")) {
            Invoke-Gcloud secrets create $Name --project $Project --replication-policy automatic --labels $Label *> $null
        }
        Invoke-Gcloud secrets versions add $Name --project $Project --data-file $tmp *> $null
    } finally { Remove-Item $tmp -Force }
}

function Step-Secrets {
    foreach ($name in @("PANTRY_TELEGRAM_BOT_TOKEN", "PANTRY_ANTHROPIC_API_KEY")) {
        if (-not $Dot[$name]) { throw "$name is missing from .env" }
        Set-Secret $name $Dot[$name]
    }
    # Generated once; rotating it would need a new setWebhook.
    if (-not (Test-Gcloud "secrets describe PANTRY_TELEGRAM_WEBHOOK_SECRET --project $Project")) {
        $alphabet = [char[]]"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
        $bytes = [byte[]]::new(48)
        [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
        Set-Secret "PANTRY_TELEGRAM_WEBHOOK_SECRET" (-join ($bytes | ForEach-Object { $alphabet[$_ % 64] }))
    }
    foreach ($name in $SecretNames) {
        Invoke-Gcloud secrets add-iam-policy-binding $name --project $Project `
            --member "serviceAccount:$RunAs" --role roles/secretmanager.secretAccessor *> $null
    }
    Write-Host "Secrets stored: $($SecretNames.Count) (values not shown)."
}

function Step-Model {
    foreach ($f in $ModelFiles) { Invoke-Gcloud storage cp $f "gs://$ModelBucket/models/" --project $Project *> $null }
    Write-Host "Model uploaded to the private models bucket."
}

function Step-Build {
    Invoke-Gcloud builds submit --project $Project --region $Region --config cloudbuild.yaml `
        --substitutions "_IMAGE=$(Get-Image),_MODELS_BUCKET=$ModelBucket" `
        --service-account "projects/$Project/serviceAccounts/$BuildAs" .
}

function Step-Deploy {
    $url = Get-ServiceUrl
    $envVars = "^;^GOOGLE_CLOUD_PROJECT=$Project;TELEGRAM_ALLOWED_CHAT_IDS=$AllowedChatIds;" +
        "PANTRY_BUCKET=$($PhotoBucket -replace '^gs://','');PANTRY_SERVICE_URL=$url;PANTRY_SCHEDULER_EMAIL=$SchedulerAs"
    $secrets = ($SecretNames | ForEach-Object { "$_=$($_):latest" }) -join ","
    Invoke-Gcloud run deploy $Service --project $Project --region $Region --image (Get-Image) `
        --service-account $RunAs --min-instances 0 --max-instances 1 --concurrency 1 `
        --memory 2Gi --cpu 1 --cpu-boost --timeout 60 --allow-unauthenticated --labels $Label `
        --set-env-vars $envVars --set-secrets $secrets
}

function Step-Webhook {
    $token = (& gcloud secrets versions access latest --secret PANTRY_TELEGRAM_BOT_TOKEN --project $Project) -join ""
    $secret = (& gcloud secrets versions access latest --secret PANTRY_TELEGRAM_WEBHOOK_SECRET --project $Project) -join ""
    $body = @{
        url                  = "$(Get-ServiceUrl)/telegram/webhook"
        secret_token         = $secret
        max_connections      = 1
        allowed_updates      = @("message", "callback_query")
        drop_pending_updates = $true
    } | ConvertTo-Json
    # The token is in the URL, so failures report the status code only.
    try {
        $set = Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$token/setWebhook" `
            -ContentType "application/json" -Body $body
        $info = Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/getWebhookInfo"
    } catch {
        throw "Telegram call failed with status $($_.Exception.Response.StatusCode)"
    }
    Write-Host "setWebhook ok: $($set.ok); max_connections: $($info.result.max_connections); last error: $($info.result.last_error_message)"
}

function Step-Scheduler {
    $url = Get-ServiceUrl
    $verb = if (Test-Gcloud "scheduler jobs describe pantry-morning --location $Region --project $Project") { "update" } else { "create" }
    Invoke-Gcloud scheduler jobs $verb http pantry-morning --location $Region --project $Project `
        --schedule "30 7 * * *" --time-zone "Asia/Jerusalem" --uri "$url/tasks/morning" --http-method POST `
        --oidc-service-account-email $SchedulerAs --oidc-token-audience $url *> $null
    Write-Host "Scheduler job pantry-morning: $verb done (07:30 Asia/Jerusalem)."
}

function Step-Budget {
    $account = ((& gcloud billing projects describe $Project --format "value(billingAccountName)") -join "") -replace "^billingAccounts/", ""
    if (-not $account) { throw "cannot read the billing account" }
    $existing = & gcloud billing budgets list --billing-account $account --filter "displayName=""$BudgetName""" --format "value(name)"
    if ($existing) { Write-Host "Budget exists."; return }
    Invoke-Gcloud billing budgets create --billing-account $account --display-name $BudgetName `
        --budget-amount $BudgetAmount --filter-projects "projects/$Project" --filter-labels $Label `
        --threshold-rule percent=0.5 --threshold-rule percent=0.9 --threshold-rule percent=1.0 *> $null
    Write-Host "Budget created: $BudgetAmount on resources labelled $Label, alerts at 50/90/100%."
}

switch ($Step) {
    "check" { Step-Check }
    "setup" { Step-Setup }
    "secrets" { Step-Secrets }
    "model" { Step-Model }
    "build" { Step-Check; Step-Build }
    "deploy" { Step-Check; Step-Deploy }
    "webhook" { Step-Webhook }
    "scheduler" { Step-Scheduler }
    "budget" { Step-Budget }
    "all" { Step-Check; Step-Setup; Step-Secrets; Step-Model; Step-Build; Step-Deploy; Step-Webhook; Step-Scheduler; Step-Budget }
}

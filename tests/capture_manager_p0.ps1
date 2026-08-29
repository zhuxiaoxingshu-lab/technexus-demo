param(
    [Parameter(Mandatory = $true)]
    [string]$TestDatabase
)

$ErrorActionPreference = "Stop"
$runId = [Guid]::NewGuid().ToString("N")
$tempRoot = (Resolve-Path "../.codex_tmp").Path
$adminConfig = Join-Path $tempRoot "capture-admin-$runId.json"
$serverOut = Join-Path $tempRoot "capture-server-$runId.out.log"
$serverErr = Join-Path $tempRoot "capture-server-$runId.err.log"
$chromeProfile = Join-Path $tempRoot "capture-chrome-$runId"
$outputDir = Join-Path (Get-Location).Path "output/manager_p0_local_qa"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$adminPassword = "P0-Admin-Local-2026"
$managerPassword = "P0-Manager-Local-2026"
$oldDb = $env:TECHNEXUS_DB_FILE
$oldConfig = $env:TECHNEXUS_ADMIN_CONFIG_FILE
$oldUser = $env:TECHNEXUS_ADMIN_USERNAME
$oldPassword = $env:TECHNEXUS_ADMIN_PASSWORD
$env:TECHNEXUS_DB_FILE = $TestDatabase
$env:TECHNEXUS_ADMIN_CONFIG_FILE = $adminConfig
$env:TECHNEXUS_ADMIN_USERNAME = "p0-admin"
$env:TECHNEXUS_ADMIN_PASSWORD = $adminPassword

$server = Start-Process python `
    -ArgumentList @("technexus_app/app.py", "--host", "127.0.0.1", "--port", "8023", "--no-browser") `
    -WorkingDirectory (Get-Location).Path `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $serverOut `
    -RedirectStandardError $serverErr

$env:TECHNEXUS_DB_FILE = $oldDb
$env:TECHNEXUS_ADMIN_CONFIG_FILE = $oldConfig
$env:TECHNEXUS_ADMIN_USERNAME = $oldUser
$env:TECHNEXUS_ADMIN_PASSWORD = $oldPassword
$chrome = $null

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            Invoke-RestMethod "http://127.0.0.1:8023/api/stats" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch {
            Start-Sleep -Milliseconds 400
        }
    }
    if (-not $ready) { throw "Local server did not become ready." }

    $chrome = Start-Process "C:/Program Files/Google/Chrome/Application/chrome.exe" `
        -ArgumentList @(
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--remote-debugging-port=9333",
            "--user-data-dir=$chromeProfile",
            "about:blank"
        ) `
        -PassThru `
        -WindowStyle Hidden

    $debugReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            Invoke-RestMethod "http://127.0.0.1:9333/json/version" -TimeoutSec 2 | Out-Null
            $debugReady = $true
            break
        } catch {
            Start-Sleep -Milliseconds 300
        }
    }
    if (-not $debugReady) { throw "Headless Chrome did not become ready." }

    node tests/capture_manager_p0_views.mjs `
        9333 `
        $outputDir `
        "http://127.0.0.1:8023" `
        "13900005678" `
        $managerPassword `
        "p0-admin" `
        $adminPassword

    Get-ChildItem $outputDir | Select-Object Name, Length, LastWriteTime
} finally {
    if ($chrome -and -not $chrome.HasExited) { Stop-Process -Id $chrome.Id -Force }
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force }
}

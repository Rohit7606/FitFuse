# FitFuse — start the API and the frontend together.
#
#     .\demo.ps1
#
# Removes one class of stage error (PERSON_B.md §8). Ctrl+C stops both.
#
# uvicorn runs WITHOUT --reload on purpose: the file watcher can restart the
# backend mid-presentation, and the demo is eight steps against one process.
#
# Owner: Person B

param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173,
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$procs = @()

function Stop-Everything {
    foreach ($p in $script:procs) {
        if ($p -and -not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

try {
    Write-Host "Starting the API on port $ApiPort ..." -ForegroundColor Cyan
    $api = Start-Process -PassThru -NoNewWindow -WorkingDirectory $root `
        -FilePath "python" `
        -ArgumentList @("-m", "uvicorn", "api.main:app", "--port", "$ApiPort")
    $procs += $api

    # Wait for the backend to actually answer before starting the frontend —
    # the first render calls /api/market, and a page that loads half a second
    # early shows an error state on stage.
    #
    # Wait on the socket rather than polling /health over HTTP. Invoke-RestMethod
    # in a tight retry loop proved unreliable here: it kept timing out against a
    # server that was already serving. A TCP connect is unambiguous, and 127.0.0.1
    # is explicit because `localhost` resolves to ::1 first on this machine while
    # uvicorn binds IPv4 only.
    $ready = $false
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($api.HasExited) {
            throw "The API exited with code $($api.ExitCode) — is port $ApiPort already in use?"
        }
        $probe = New-Object System.Net.Sockets.TcpClient
        try {
            $probe.Connect("127.0.0.1", $ApiPort)
            $ready = $probe.Connected
        } catch {
            Start-Sleep -Milliseconds 300
        } finally {
            $probe.Close()
        }
        if ($ready) { break }
    }
    if (-not $ready) { throw "The API did not open port $ApiPort within $TimeoutSeconds seconds." }

    $health = Invoke-RestMethod "http://127.0.0.1:$ApiPort/health" -TimeoutSec 10
    if ($health.status -ne "ok") {
        throw "The API is up but reports status '$($health.status)' for $($health.market)."
    }

    Write-Host ("  ok - {0} invoices, {1} providers from {2}" -f `
        $health.invoices, $health.providers, $health.market) -ForegroundColor Green

    $npm = (Get-Command npm -ErrorAction SilentlyContinue).Source
    if (-not $npm) { throw "npm is not on PATH; cannot start the frontend." }

    Write-Host "Starting the frontend on port $WebPort (live mode) ..." -ForegroundColor Cyan
    $web = Start-Process -PassThru -NoNewWindow -WorkingDirectory (Join-Path $root "web") `
        -FilePath $npm -ArgumentList @("run", "dev:live")
    $procs += $web

    Write-Host ""
    Write-Host "  API   http://localhost:$ApiPort/health" -ForegroundColor Yellow
    Write-Host "  Docs  http://localhost:$ApiPort/docs"   -ForegroundColor Yellow
    Write-Host "  Demo  http://localhost:$WebPort"        -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Ctrl+C stops both." -ForegroundColor DarkGray

    Wait-Process -Id $api.Id, $web.Id
} finally {
    Stop-Everything
}

# start.ps1 — Launch all 5 MarketVentures services
# Usage: .\start.ps1 [-Force]  (-Force kills any existing process on each port)
param([switch]$Force)

$services = @(
    @{ name = "price-recon";     dir = "price-recon";     cmd = "python -m uvicorn api.routes:app --host 0.0.0.0 --port 8000"; port = 8000 },
    @{ name = "market-data-hub"; dir = "market-data-hub"; cmd = "python -m uvicorn api.routes:app --host 0.0.0.0 --port 8001"; port = 8001 },
    @{ name = "alpha-pipeline";  dir = "alpha-pipeline";  cmd = "streamlit run dashboard/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true"; port = 8501 },
    @{ name = "data-onboard";    dir = "data-onboard";    cmd = "python -m uvicorn api.routes:app --host 0.0.0.0 --port 8003"; port = 8003 },
    @{ name = "market-ops";      dir = "market-ops";      cmd = "python -m uvicorn api.routes:app --host 0.0.0.0 --port 8004"; port = 8004 }
)

$root = $PSScriptRoot

foreach ($svc in $services) {
    $port = $svc.port

    # Check for existing listener on this port
    $existing = netstat -ano | Select-String "0\.0\.0\.0:$port\s.*LISTENING|127\.0\.0\.1:$port\s.*LISTENING" | ForEach-Object {
        ($_ -split '\s+')[-1]
    } | Select-Object -Unique

    if ($existing) {
        if ($Force) {
            foreach ($pid in $existing) {
                try {
                    Stop-Process -Id $pid -Force -ErrorAction Stop
                    Write-Host "  killed PID $pid on :$port" -ForegroundColor Yellow
                } catch { }
            }
            Start-Sleep -Milliseconds 300
        } else {
            Write-Host "[$($svc.name)] port :$port already in use (PID $($existing -join ', ')). Use -Force to kill and restart." -ForegroundColor Red
            continue
        }
    }

    $svcDir = Join-Path $root $svc.dir
    $logFile = Join-Path $root "logs\$($svc.name).log"
    New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null

    $cmdParts = $svc.cmd -split ' ', 2
    Start-Process -FilePath $cmdParts[0] -ArgumentList $cmdParts[1] `
        -WorkingDirectory $svcDir `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError "$logFile.err" `
        -WindowStyle Hidden

    Write-Host "[$($svc.name)] started on :$port  (log: logs\$($svc.name).log)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Dashboards:" -ForegroundColor Cyan
Write-Host "  price-recon      http://localhost:8000"
Write-Host "  market-data-hub  http://localhost:8001"
Write-Host "  alpha-pipeline   http://localhost:8501"
Write-Host "  data-onboard     http://localhost:8003"
Write-Host "  market-ops       http://localhost:8004"

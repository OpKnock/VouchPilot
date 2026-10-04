# VouchPilot one-command startup: llama server (if weights exist) + FastAPI backend
# serving the API and the premium web UI, then opens the browser.
# Usage: double-click start-vouchpilot.bat, or:
# powershell -ExecutionPolicy Bypass -File start-vouchpilot.ps1
$ErrorActionPreference = "SilentlyContinue"
Set-Location $PSScriptRoot

$serverUp = $false
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -TimeoutSec 3 -UseBasicParsing
    if ($r.StatusCode -eq 200) { $serverUp = $true }
} catch {}

$weights = Get-ChildItem "models\*.gguf" -ErrorAction SilentlyContinue | Select-Object -First 1
$serverExe = "tools\llama-server\bin\llama-server.exe"
if (-not $serverUp -and $weights -and (Test-Path $serverExe)) {
    Write-Output ("Starting llama server with " + $weights.Name + " ...")
    Start-Process -FilePath (Join-Path $PSScriptRoot $serverExe) -ArgumentList "-m", ("models\" + $weights.Name), "--host", "127.0.0.1", "--port", "8080", "-c", "4096", "--n-gpu-layers", "99", "--cache-type-k", "q8_0", "--cache-type-v", "q8_0", "--log-disable" -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 5
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -TimeoutSec 3 -UseBasicParsing
            if ($r.StatusCode -eq 200) { $serverUp = $true; break }
        } catch {}
    }
}
if ($serverUp) { Write-Output "llama server: OK (server scorer available)" }
else { Write-Output "llama server: skipped (keyword/stub/vouchpilot need no server)" }

if (Test-Path "web\dist\index.html") { Write-Output "Web UI: premium build found" }
else { Write-Output "Web UI: web\dist missing - run: cd web; npm install; npm run build" }

Write-Output "Starting VouchPilot backend on http://127.0.0.1:8000 ..."
Write-Output "Open that URL in your browser (no tab is opened automatically)."
python -m uvicorn vouch_engine.api:create_app --factory --host 127.0.0.1 --port 8000

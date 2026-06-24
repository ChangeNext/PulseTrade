$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$requirements = Join-Path $backendDir "requirements.txt"
$viteScript = Join-Path $frontendDir "node_modules\vite\bin\vite.js"

Write-Host ""
Write-Host "  PulseTrade development launcher" -ForegroundColor Cyan
Write-Host "  --------------------------------" -ForegroundColor DarkGray

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "[setup] Creating backend virtual environment..." -ForegroundColor Yellow
    python -m venv (Join-Path $backendDir ".venv")
}

& $venvPython -c "import fastapi, sqlalchemy, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[setup] Installing backend dependencies..." -ForegroundColor Yellow
    & $venvPython -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
}

if (-not (Test-Path -LiteralPath $viteScript)) {
    Write-Host "[setup] Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $frontendDir
    try { npm.cmd install } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
}

$node = (Get-Command node.exe -ErrorAction Stop).Source
$backend = $null
$frontend = $null

try {
    Write-Host "[start] Backend  http://127.0.0.1:8000" -ForegroundColor Green
    $backend = Start-Process `
        -FilePath $venvPython `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $backendDir `
        -NoNewWindow `
        -PassThru

    Write-Host "[start] Frontend http://127.0.0.1:5173" -ForegroundColor Green
    $frontend = Start-Process `
        -FilePath $node `
        -ArgumentList $viteScript, "--host", "127.0.0.1", "--port", "5173" `
        -WorkingDirectory $frontendDir `
        -NoNewWindow `
        -PassThru

    Write-Host ""
    Write-Host "Press Ctrl+C to stop both servers." -ForegroundColor DarkGray

    while (-not $backend.HasExited -and -not $frontend.HasExited) {
        Start-Sleep -Milliseconds 500
        $backend.Refresh()
        $frontend.Refresh()
    }

    if ($backend.HasExited) {
        $backend.WaitForExit()
        throw "Backend stopped unexpectedly (exit code $($backend.ExitCode))."
    }
    if ($frontend.HasExited) {
        $frontend.WaitForExit()
        throw "Frontend stopped unexpectedly (exit code $($frontend.ExitCode))."
    }
}
finally {
    Write-Host ""
    Write-Host "[stop] Stopping PulseTrade servers..." -ForegroundColor Yellow
    if ($backend -and -not $backend.HasExited) { Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue }
    if ($frontend -and -not $frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
}

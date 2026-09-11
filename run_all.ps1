# TrustRAG PowerShell Launcher
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "              Starting TrustRAG Local Lab" -ForegroundColor Green
Write-Host "      Maintained by Md. Fahim Istiaq Siam" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

$pythonExe = if (Test-Path "$PSScriptRoot\.venv\Scripts\python.exe") { "$PSScriptRoot\.venv\Scripts\python.exe" } else { "python" }

$ollamaCheck = Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue
if (-not $ollamaCheck) {
    $ollamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (Test-Path $ollamaExe) {
        Write-Host "Starting Ollama service..." -ForegroundColor Cyan
        Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
    }
}

Write-Host "`nStarting TrustRAG Backend (FastAPI on http://127.0.0.1:8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$pythonExe' -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload"

Write-Host "Starting TrustRAG Webapp (Next.js on http://localhost:3000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\webapp'; cmd.exe /c 'npm run dev'"

Write-Host "`n[✓] Both servers are starting in separate terminal windows!" -ForegroundColor Cyan
Write-Host "Backend API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Yellow
Write-Host "Webapp Dashboard: http://localhost:3000" -ForegroundColor Yellow

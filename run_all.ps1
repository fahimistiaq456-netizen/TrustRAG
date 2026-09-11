# TrustRAG PowerShell Launcher
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "              Starting TrustRAG Local Lab" -ForegroundColor Green
Write-Host "      Maintained by Md. Fahim Istiaq Siam" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

Write-Host "`nStarting TrustRAG Backend (FastAPI on http://127.0.0.1:8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload"

Write-Host "Starting TrustRAG Webapp (Next.js on http://localhost:3000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location webapp; npm run dev"

Write-Host "`n[✓] Both servers are starting in separate terminal windows!" -ForegroundColor Cyan
Write-Host "Backend API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Yellow
Write-Host "Webapp Dashboard: http://localhost:3000" -ForegroundColor Yellow

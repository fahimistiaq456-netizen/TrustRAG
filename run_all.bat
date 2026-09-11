@echo off
title TrustRAG Local Lab Launcher
echo ========================================================
echo               Starting TrustRAG Local Lab
echo       Maintained by Md. Fahim Istiaq Siam
echo ========================================================
echo.

set PYTHON_CMD=python
if exist ".venv\Scripts\python.exe" set PYTHON_CMD=.venv\Scripts\python.exe

echo Starting TrustRAG Backend (FastAPI on http://127.0.0.1:8000)...
start "TrustRAG Backend" cmd /k "%PYTHON_CMD% -m uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload"

echo Starting TrustRAG Webapp (Next.js on http://localhost:3000)...
cd webapp
start "TrustRAG Webapp" cmd /k "npm run dev"
cd ..

echo.
echo ========================================================
echo [OK] Both servers are starting up in separate windows!
echo - API Docs: http://127.0.0.1:8000/docs
echo - Web UI:  http://localhost:3000
echo ========================================================
echo.
pause

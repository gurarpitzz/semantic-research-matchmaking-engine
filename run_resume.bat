@echo off
echo 🛡️  SRME: Resume Startup Script (No Data Loss)
echo --------------------------------------------

echo 🛑 Stopping any conflicting SRME processes...
taskkill /F /IM uvicorn.exe /T 2>NUL
:: We diligently try to only kill the server, but run_local uses a python wrapper
taskkill /F /IM python.exe /T 2>NUL

echo 🚀 Starting SRME Server (Data Preserved)...
echo    Dashboard: http://localhost:8001
.\venv\Scripts\python.exe -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8001
pause

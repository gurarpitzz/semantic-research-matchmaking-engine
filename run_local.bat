@echo off
echo 🛡️  SRME: Ultimate Startup Script
echo ----------------------------------

echo 🛑 Stopping any existing SRME processes...
taskkill /F /IM python.exe /T 2>NUL
taskkill /F /IM uvicorn.exe /T 2>NUL

echo 🧹 Cleaning cache...
powershell -Command "Get-ChildItem -Path . -Filter __pycache__ -Recurse | Remove-Item -Force -Recurse"

echo 🗄️  Resetting database...
.\venv\Scripts\python.exe -c "import sqlite3, os; db_path = 'data/srme.db'; os.makedirs('data', exist_ok=True); conn = sqlite3.connect(db_path); c = conn.cursor(); tables = ['professors', 'papers', 'authors', 'paper_authors', 'paper_embeddings', 'ingestion_jobs']; [c.execute(f'DROP TABLE IF EXISTS {t}') for t in tables]; conn.commit(); conn.close(); print('Database purged')"

echo 🚀 Starting SRME Standalone Server...
.\venv\Scripts\python.exe -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8001
pause

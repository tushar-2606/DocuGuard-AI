@echo off
setlocal
set "ROOT=%~dp0"

where.exe py >nul 2>&1
if errorlevel 1 (
  echo Python Launcher "py" was not found. Install Python and try again.
  pause
  exit /b 1
)

where.exe npm >nul 2>&1
if errorlevel 1 (
  echo npm was not found. Install Node.js and try again.
  pause
  exit /b 1
)

py -c "import fastapi, uvicorn, fitz, dateparser" >nul 2>&1
if errorlevel 1 (
  echo Installing backend dependencies...
  py -m pip install -r "%ROOT%backend\requirements.txt"
  if errorlevel 1 (
    echo Backend dependency installation failed.
    pause
    exit /b 1
  )
)

if not exist "%ROOT%frontend\node_modules" (
  echo Installing frontend dependencies...
  call npm.cmd --prefix "%ROOT%frontend" install
  if errorlevel 1 (
    echo Frontend dependency installation failed.
    pause
    exit /b 1
  )
)

start "DocuGuard Backend" cmd /k "cd /d ""%ROOT%backend"" && py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
start "DocuGuard Frontend" cmd /k "cd /d ""%ROOT%frontend"" && npm.cmd run dev -- --host 127.0.0.1"

echo.
echo DocuGuard is starting. Keep both terminal windows open.
echo Open http://localhost:5173 in your browser.

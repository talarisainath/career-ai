@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

rem Serve the frontend folder (this script's location) over local HTTP.
cd /d "%~dp0"

set "PY_EXE="
if exist "backend\.venv\Scripts\python.exe" set "PY_EXE=backend\.venv\Scripts\python.exe"

if not defined PY_EXE (
  for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python311\tools\python.exe"
    "C:\Python311\python.exe"
    "C:\Python312\python.exe"
    "C:\Python313\python.exe"
  ) do (
    if not defined PY_EXE if exist "%%~P" set "PY_EXE=%%~P"
  )
)

if not defined PY_EXE (
  for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%I"
)
if not defined PY_EXE (
  for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%I"
)

if not defined PY_EXE (
  echo.
  echo [ERROR] Python 3.11 or newer was not found, so the local web server
  echo cannot start. Install Python from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH", then run this script again.
  echo.
  echo The site can still be opened by double-clicking index.html, but the
  echo live API and recommendations require serving it over HTTP.
  echo.
  pause
  exit /b 1
)

echo Serving CareerAI at http://127.0.0.1:5500
echo Start the API separately with run-backend.bat.
echo Press Ctrl+C to stop the server.
echo.

"%PY_EXE%" -m http.server 5500 --bind 127.0.0.1
if errorlevel 1 (
  echo.
  echo [ERROR] The frontend server stopped. Port 5500 may already be in use.
  echo.
  pause
)

endlocal

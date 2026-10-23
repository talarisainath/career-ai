@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

rem Always run from the backend directory, wherever the script is launched from.
cd /d "%~dp0backend"

set "PY_EXE="
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

if not defined PY_EXE (
  for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%I"
)
if not defined PY_EXE (
  for /f "delims=" %%I in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PY_EXE=%%I"
)

if not defined PY_EXE (
  echo.
  echo [ERROR] Python 3.11 or newer was not found.
  echo.
  echo Install it from https://www.python.org/downloads/ and tick
  echo "Add python.exe to PATH" during setup, then run this script again.
  echo.
  pause
  exit /b 1
)

echo Using Python: "%PY_EXE%"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment in backend\.venv ...
  "%PY_EXE%" -m venv .venv
  if errorlevel 1 (
    echo.
    echo [ERROR] Could not create the virtual environment.
    echo Check that the Python installation includes the venv module.
    echo.
    pause
    exit /b 1
  )
)

echo Installing / updating backend requirements ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERROR] Dependency installation failed.
  echo Check your internet connection and try:
  echo   backend\.venv\Scripts\python.exe -m pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo.
echo CareerAI API:  http://127.0.0.1:8000
echo API docs:      http://127.0.0.1:8000/docs
echo Frontend:      http://127.0.0.1:5500  (start run-frontend.bat)
echo.
echo Press Ctrl+C to stop the server.
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
if errorlevel 1 (
  echo.
  echo [ERROR] The API server exited unexpectedly.
  echo If port 8000 is already in use, stop the other process and try again.
  echo.
  pause
)

endlocal

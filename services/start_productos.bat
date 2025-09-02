@echo off
setlocal
cd /d "%~dp0productos"
if not exist "venv\Scripts\python.exe" (
  echo [productos] creando venv...
  where py >nul 2>nul && (py -3 -m venv venv) || (python -m venv venv)
)
call "venv\Scripts\activate.bat"
echo [productos] instalando deps...
python -m pip install -r requirements.txt
set SERVICE_TOKEN=penguin-secret
set PORT=5001
echo [productos] arrancando en %PORT%...
python app.py
echo.
echo [productos] terminado. Exit code %ERRORLEVEL%
pause

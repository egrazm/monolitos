@echo off
setlocal
cd /d "%~dp0pagos"
if not exist "venv\Scripts\python.exe" (
  echo [pagos] creando venv...
  where py >nul 2>nul && (py -3 -m venv venv) || (python -m venv venv)
)
call "venv\Scripts\activate.bat"
echo [pagos] instalando deps...
python -m pip install -r requirements.txt
set SERVICE_TOKEN=penguin-secret
set PORT=5003
echo [pagos] arrancando en %PORT%...
python app.py
echo.
echo [pagos] terminado. Exit code %ERRORLEVEL%
pause

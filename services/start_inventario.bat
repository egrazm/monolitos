@echo off
setlocal
cd /d "%~dp0inventario"
if not exist "venv\Scripts\python.exe" (
  echo [inventario] creando venv...
  where py >nul 2>nul && (py -3 -m venv venv) || (python -m venv venv)
)
call "venv\Scripts\activate.bat"
echo [inventario] instalando deps...
python -m pip install -r requirements.txt
set SERVICE_TOKEN=penguin-secret
set PORT=5002
echo [inventario] arrancando en %PORT%...
python app.py
echo.
echo [inventario] terminado. Exit code %ERRORLEVEL%
pause

@echo off
setlocal ENABLEDELAYEDEXPANSION

REM === 1) Resolver carpeta del servicio (soporta espacios) ===
set "SERVICE_DIR=%~dp0pedidos"
echo [pedidos] SERVICE_DIR="%SERVICE_DIR%"

if not exist "%SERVICE_DIR%\app.py" (
  echo [pedidos] ERROR: no encuentro app.py en "%SERVICE_DIR%"
  echo [pedidos] Verificá que este .bat esté en: ...\penguin-microservicios\services\
  pause & exit /b 1
)

REM OJO: nunca pongas la ruta sola en una línea. Usá pushd/cd.
pushd "%SERVICE_DIR%" || (echo [pedidos] ERROR al entrar en "%SERVICE_DIR%" & pause & exit /b 1)
echo [pedidos] CWD="%CD%"

REM === 2) Python y venv ===
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

if not exist "venv\Scripts\python.exe" (
  echo [pedidos] creando venv...
  %PY% -m venv venv || (echo [pedidos] ERROR creando venv & pause & exit /b 1)
)

call "venv\Scripts\activate.bat" || (echo [pedidos] ERROR activando venv & pause & exit /b 1)

REM === 3) Dependencias ===
echo [pedidos] instalando deps...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt || (echo [pedidos] ERROR en pip install & pause & exit /b 1)

REM === 4) Variables requeridas ===
set "SERVICE_TOKEN=penguin-secret"
set "PORT=5004"
set "PRODUCTS_URL=http://127.0.0.1:5001"
set "INVENTORY_URL=http://127.0.0.1:5002"
set "PAYMENTS_URL=http://127.0.0.1:5003"

echo [pedidos] PORT=%PORT%
echo [pedidos] PRODUCTS_URL=%PRODUCTS_URL%
echo [pedidos] INVENTORY_URL=%INVENTORY_URL%
echo [pedidos] PAYMENTS_URL=%PAYMENTS_URL%

REM === 5) Lanzar el servicio ===
echo [pedidos] arrancando Flask...
python app.py

echo.
echo [pedidos] terminado. Exit code %ERRORLEVEL%
pause

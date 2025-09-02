@echo off
setlocal
cd /d "%~dp0"
start "" "%ComSpec%" /k ""%~dp0start_productos.bat"
start "" "%ComSpec%" /k ""%~dp0start_inventario.bat"
start "" "%ComSpec%" /k ""%~dp0start_pagos.bat"
start "" "%ComSpec%" /k ""%~dp0start_pedidos.bat"

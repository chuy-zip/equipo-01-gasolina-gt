@echo off
rem Doble clic en Windows para abrir la presentacion. Cierra esta ventana para apagarla.
cd /d "%~dp0"
python servir.py
if errorlevel 1 py servir.py
pause

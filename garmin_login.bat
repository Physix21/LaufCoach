@echo off
cd /d "%~dp0"
python scripts\setup_garmin.py
if errorlevel 1 goto done
"%LOCALAPPDATA%\Laufcoach\venv\Scripts\python.exe" scripts\garmin_sync.py login
:done
pause

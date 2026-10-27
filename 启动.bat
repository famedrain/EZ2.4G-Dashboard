@echo off
setlocal
cd /d "%~dp0"
where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw -3 "%~dp0my_devices.py"
    exit /b
)
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%~dp0my_devices.py"
    exit /b
)
echo Python 3.10+ with tkinter is required. Or download the EXE from Releases.
pause

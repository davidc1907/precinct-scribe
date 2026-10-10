@echo off
rem Double click: opens the app. With options: runs the command line version.

if not exist "%~dp0.venv\Scripts\python.exe" (
    echo precinct-scribe is not installed yet. Please double click install.bat first.
    pause
    exit /b 1
)

if "%~1"=="" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0gui.py"
    exit /b 0
)

"%~dp0.venv\Scripts\python.exe" "%~dp0scribe.py" %*

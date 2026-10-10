@echo off
cd /d "%~dp0"

set "PY=python"

python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 or newer was not found.
    where winget >nul 2>nul
    if errorlevel 1 (
        echo Please install Python from https://www.python.org/downloads/
        echo Check "Add python.exe to PATH" during setup, then run install.bat again.
        pause
        exit /b 1
    )
    echo Installing Python 3.13 with winget...
    winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo The Python installation failed. Please install it from https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
)

if not "%PY%"=="python" if not exist "%PY%" (
    echo Python was installed, but could not be found.
    echo Please close this window and run install.bat again.
    pause
    exit /b 1
)

"%PY%" -m venv .venv
if errorlevel 1 (
    echo Could not create the virtual environment.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip

where nvidia-smi >nul 2>nul
if errorlevel 1 (
    echo No NVIDIA GPU found, installing the CPU version.
    python -m pip install -r requirements.txt
    if errorlevel 1 goto failed
    echo Downloading the Whisper model small ^(about 0.5 GB^)...
    python -c "from faster_whisper.utils import download_model; download_model('small')"
    if errorlevel 1 goto failed
) else (
    echo NVIDIA GPU found, installing the GPU version.
    python -m pip install -r requirements-gpu.txt
    if errorlevel 1 goto failed
    echo Downloading the Whisper model large-v3 ^(about 3 GB^), this can take a while...
    python -c "from faster_whisper.utils import download_model; download_model('large-v3')"
    if errorlevel 1 goto failed
)

where deno >nul 2>nul
if errorlevel 1 (
    where winget >nul 2>nul
    if errorlevel 1 (
        echo Deno could not be installed automatically. YouTube links may show a warning.
    ) else (
        echo Installing Deno for YouTube support...
        winget install -e --id DenoLand.Deno --accept-package-agreements --accept-source-agreements
    )
)

echo.
echo Installation finished. Double click scribe.bat to open precinct-scribe.
pause
exit /b 0

:failed
echo.
echo The installation failed. Please check your internet connection and try again.
echo If it still fails, open an issue and include the error message above.
pause
exit /b 1
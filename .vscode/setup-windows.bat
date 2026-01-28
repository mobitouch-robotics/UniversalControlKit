@echo off
REM Setup Python environment for Windows
REM Usage: setup-windows.bat [--cache]
REM   --cache : if present, keep and reuse existing .venv (skip setup when .venv exists)
REM             if absent, remove any existing .venv and rebuild it

setlocal EnableDelayedExpansion
set "CACHE=0"
for %%A in (%*) do (
    if "%%~A"=="/cache" set "CACHE=1"
)

if "%CACHE%"=="1" (
    if exist .venv (
        echo Using cached virtual environment (.venv); skipping setup.
        exit /b 0
    )
) else (
    if exist .venv (
        echo Removing existing .venv
        rd /s /q .venv
    )
)

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
    
    echo Upgrading pip, setuptools, and wheel...
    .venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
    
    echo Installing av package...
    .venv\Scripts\python.exe -m pip install --only-binary=av "av>=14.0.0,<15.0.0"
    
    echo Installing unitree_webrtc_connect...
    .venv\Scripts\python.exe -m pip install git+https://github.com/legion1581/unitree_webrtc_connect.git@v2.0.4
    
    echo Installing moderngl, Pillow, PyQt5...
    .venv\Scripts\python.exe -m pip install moderngl Pillow PyQt5

    echo Installing pywavefront...
    .venv\Scripts\python.exe -m pip install pywavefront

    echo Installing pygame...
    .venv\Scripts\python.exe -m pip install pygame

    echo Environment setup complete!
) else (
    echo Virtual environment already exists.
)

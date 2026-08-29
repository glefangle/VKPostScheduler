@echo off
setlocal
cd /d "%~dp0"

REM runs build_exe.py: generates a size-optimized spec, builds dist\PostScheduler.exe

set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"

%PY% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install it or create the venv via run.bat
    pause
    exit /b 1
)

%PY% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 %PY% -m pip install "pyinstaller>=6.0"
if errorlevel 1 goto :fail

%PY% -c "import PyQt5, requests, vk_api, PIL, keyring" >nul 2>&1
if errorlevel 1 %PY% -m pip install -e .
if errorlevel 1 goto :fail

%PY% build_exe.py
if errorlevel 1 goto :fail

pause
exit /b 0

:fail
echo.
echo BUILD FAILED - see output above
pause
exit /b 1

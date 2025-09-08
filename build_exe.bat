@echo off
echo ========================================
echo Building Single File Executable
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo Python found: 
python --version
echo.

REM Check if PyInstaller is installed
echo Checking PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller>=6.0.0
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)

echo PyInstaller is available
echo.

REM Clean previous builds
echo Cleaning previous builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "*.spec" del /q "*.spec"
echo.

REM Build the executable
echo Building executable...
echo Command: pyinstaller --onefile --windowed --name=PostScheduler --icon=icon.ico main.py
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name=PostScheduler ^
    --add-data="vk_config.py;." ^
    --hidden-import=vk_api ^
    --hidden-import=PyQt5 ^
    --hidden-import=PyQt5.QtCore ^
    --hidden-import=PyQt5.QtWidgets ^
    --hidden-import=PyQt5.QtGui ^
    --hidden-import=requests ^
    --hidden-import=Pillow ^
    --hidden-import=PIL ^
    --collect-all=vk_api ^
    --collect-all=PyQt5 ^
    main.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    echo Check the output above for details.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo Executable location: dist\PostScheduler.exe
echo File size:
for %%A in ("dist\PostScheduler.exe") do echo %%~zA bytes

REM Test if the executable exists
if exist "dist\PostScheduler.exe" (
    echo.
    echo Build verification: SUCCESS
    echo.
    echo You can now run the standalone executable:
    echo   dist\PostScheduler.exe
    echo.
    echo Or copy it to any Windows computer and run it without Python installed.
) else (
    echo.
    echo Build verification: FAILED
    echo The executable was not created successfully.
)

echo.
pause
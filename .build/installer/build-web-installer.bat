@echo off
REM Build script for RDO Map Overlay Web Installer
REM This creates a minimal ~1-2MB installer that downloads everything during installation

echo ============================================
echo Building RDO Map Overlay Web Installer
echo ============================================
echo.

REM Check if NSIS is installed
where makensis >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: NSIS not found in PATH
    echo Please install NSIS from https://nsis.sourceforge.io/
    echo And add it to your PATH environment variable
    exit /b 1
)

REM Check for required NSIS plugins
set NSIS_DIR=
for /f "tokens=*" %%i in ('where makensis') do (
    for %%j in ("%%~dpi..") do set NSIS_DIR=%%~fj
)

if not exist "%NSIS_DIR%\Plugins\x86-unicode\INetC.dll" (
    echo ERROR: INetC plugin not found
    echo Please download from: https://nsis.sourceforge.io/INetC_plug-in
    echo And extract to: %NSIS_DIR%\Plugins\
    exit /b 1
)

if not exist "%NSIS_DIR%\Plugins\x86-unicode\nsisunz.dll" (
    echo ERROR: nsisunz plugin not found
    echo Please download from: https://nsis.sourceforge.io/Nsisunz_plug-in
    echo And extract to: %NSIS_DIR%\Plugins\
    exit /b 1
)

REM Create output directory
if not exist "..\..\build\installer" mkdir "..\..\build\installer"

REM Clean previous builds
if exist "..\..\build\installer\*.exe" del /q "..\..\build\installer\*.exe"

REM Compile the installer
echo.
echo Compiling installer...
makensis /V2 installer-main.nsi

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to compile installer
    exit /b %ERRORLEVEL%
)

REM Check output size
for %%A in ("..\..\build\installer\RDO-Map-Overlay-WebSetup-*.exe") do (
    set SIZE=%%~zA
    set /a SIZE_MB=%SIZE% / 1048576
    echo.
    echo ============================================
    echo Build Complete!
    echo Installer: %%A
    echo Size: %SIZE_MB% MB
    echo ============================================
)

echo.
echo The web installer is ready for distribution.
echo It will download ~205MB during installation.
echo Final installation size will be ~400MB.
echo.
@echo off
REM Build native Windows launcher for RDO Map Overlay

echo Building native launcher...

REM Try Visual Studio 2022 first
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
    goto :build
)

REM Try Visual Studio 2019
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
    goto :build
)

REM Try Build Tools
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
    goto :build
)

echo ERROR: Visual Studio or Build Tools not found
echo Please install Visual Studio or Build Tools for Visual Studio
echo https://visualstudio.microsoft.com/downloads/
exit /b 1

:build
cl /EHsc /O2 /MT launcher.cpp /Fe:launcher.exe /link /SUBSYSTEM:WINDOWS ws2_32.lib

if %ERRORLEVEL% NEQ 0 (
    echo Build failed!
    exit /b %ERRORLEVEL%
)

echo Build complete: launcher.exe
echo.

REM Add icon to the executable if Resource Hacker is available
where ResourceHacker >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Adding icon to launcher...
    ResourceHacker -open launcher.exe -save launcher_icon.exe -action addoverwrite -res ..\..\frontend\icon.ico -mask ICONGROUP,MAINICON,
    if exist launcher_icon.exe (
        move /Y launcher_icon.exe launcher.exe >nul
        echo Icon added successfully
    )
)

REM Sign the executable if signtool is available
where signtool >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Signing launcher...
    signtool sign /a /t http://timestamp.digicert.com launcher.exe >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo Launcher signed successfully
    )
)
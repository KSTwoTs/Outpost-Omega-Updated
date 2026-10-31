@echo off
setlocal EnableExtensions
title Build Outpost Omega EXE

rem ===================================================================
rem  Packages the game into a standalone folder + zip that runs on any
rem  Windows PC with no Python installed. Output goes to .\dist\
rem  Run "Play Outpost Omega.bat" once first so the .venv exists.
rem ===================================================================

set "ROOT=%~dp0"
cd /d "%ROOT%Outpost Omega Updated" 2>nul || (echo Could not find the "Outpost Omega Updated" folder. & pause & exit /b 1)

set "VPY=%CD%\.venv\Scripts\python.exe"
if not exist "%VPY%" (
    echo Run "Play Outpost Omega.bat" once first to set up Python and pygame-ce.
    pause
    exit /b 1
)

set "WORK=%TEMP%\outpost_omega_build"
set "DIST=%ROOT%dist"

echo Installing PyInstaller...
"%VPY%" -m pip install --disable-pip-version-check -q pyinstaller || goto :fail

echo Building. This can take a minute or two...
"%VPY%" -m PyInstaller --noconfirm --clean --windowed ^
    --name "Outpost Omega" ^
    --distpath "%DIST%" --workpath "%WORK%" --specpath "%WORK%" ^
    --add-data "%CD%\data;data" ^
    --collect-submodules game ^
    main.py || goto :fail

echo Zipping for sharing...
if exist "%DIST%\Outpost Omega.zip" del "%DIST%\Outpost Omega.zip"
powershell -NoProfile -Command "Compress-Archive -Path '%DIST%\Outpost Omega' -DestinationPath '%DIST%\Outpost Omega.zip'"

echo.
echo Done!
echo   Play it:   dist\Outpost Omega\Outpost Omega.exe
echo   Share it:  dist\Outpost Omega.zip  - unzip, then run the .exe
start "" "%DIST%"
pause
exit /b 0

:fail
echo.
echo Build failed. The error is above.
pause
exit /b 1

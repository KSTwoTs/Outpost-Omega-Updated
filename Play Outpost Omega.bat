@echo off
setlocal EnableExtensions
title Outpost Omega: Alien Siege

rem ===================================================================
rem  One-click launcher for Outpost Omega.
rem  First run: finds or installs Python, makes a private .venv inside
rem  the game folder, and installs pygame-ce into it.
rem  Every run after that: just starts the game.
rem ===================================================================

cd /d "%~dp0Outpost Omega Updated" 2>nul || goto :no_game_folder

set "VENV=%CD%\.venv"
set "VPY=%VENV%\Scripts\python.exe"

rem --- Reuse the existing environment if it still works ---------------
if exist "%VPY%" (
    "%VPY%" -c "pass" >nul 2>nul && goto :check_deps
    echo The saved game environment is broken. Rebuilding it...
    rmdir /s /q "%VENV%"
)

rem --- Find Python 3.10+ (install it if missing) ----------------------
call :find_python
if not defined PY (
    echo Python was not found on this PC.
    where winget >nul 2>nul || goto :no_python
    echo Installing Python 3.12 for your user account. This takes a minute...
    winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    call :find_python
)
if not defined PY goto :no_python

echo Setting up the game environment. First run only...
%PY% -m venv "%VENV%" || goto :fail

:check_deps
"%VPY%" -c "import pygame" >nul 2>nul && goto :run
echo Installing game requirements...
"%VPY%" -m pip install --disable-pip-version-check -q --upgrade pip >nul 2>nul
"%VPY%" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :fail

:run
echo Launching Outpost Omega...
"%VPY%" main.py
if errorlevel 1 (
    echo.
    echo The game closed with an error. The details are above.
    pause
)
exit /b 0


rem ===================================================================
:find_python
set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && (set "PY=py -3" & exit /b 0)
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && (set "PY=python" & exit /b 0)
rem A fresh winget install isn't on PATH yet in this window, so look for it directly.
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\python.exe" set "PY="%%D\python.exe""
)
exit /b 0

:no_game_folder
echo Could not find the "Outpost Omega Updated" folder next to this file.
echo Keep this launcher in the same folder as "Outpost Omega Updated".
pause
exit /b 1

:no_python
echo.
echo Python 3.10 or newer is needed and could not be installed automatically.
echo Install it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during setup, then run this file again.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:fail
echo.
echo Setup failed. Check your internet connection and try again.
echo If it keeps failing, delete the ".venv" folder inside "Outpost Omega Updated".
pause
exit /b 1

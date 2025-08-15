@echo off
REM Home Network Monitor - Windows Autostart Script
REM This script starts Docker Desktop and the monitoring services on system startup

echo ================================================
echo Home Network Monitor - Autostart Script
echo ================================================

REM Check if Docker Desktop is running, if not try to start it
echo Checking Docker Desktop status...
tasklist /FI "IMAGENAME eq Docker Desktop.exe" | findstr /i "Docker Desktop.exe" > nul
if %errorlevel% neq 0 (
    echo Starting Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    
    REM Wait for Docker to initialize (may need adjustment)
    echo Waiting 60 seconds for Docker to initialize...
    timeout /t 60 /nobreak > nul
) else (
    echo Docker Desktop is already running
)

REM Change to the project directory
cd /d "%~dp0\.."

REM Try to find Git Bash to run the shell script
set "GIT_BASH="
if exist "C:\Program Files\Git\bin\bash.exe" (
    set "GIT_BASH=C:\Program Files\Git\bin\bash.exe"
) else if exist "C:\Program Files (x86)\Git\bin\bash.exe" (
    set "GIT_BASH=C:\Program Files (x86)\Git\bin\bash.exe"
)

if not defined GIT_BASH (
    echo ERROR: Git Bash not found. Cannot run the start_monitoring.sh script.
    echo Please install Git for Windows or manually run the script.
    pause
    exit /b 1
)

REM Run the start_monitoring.sh script using Git Bash
echo Starting monitoring services...
"%GIT_BASH%" -c "./scripts/start_monitoring.sh"

echo Startup complete!
echo You can close this window
timeout /t 10
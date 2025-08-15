# Home Network Monitor - Windows Autostart Setup

This directory contains scripts to configure automatic startup of Docker Desktop and the Home Network Monitor services when your Windows system boots up.

## Autostart Scripts

1. `autostart_monitoring.bat` - A Windows batch script that:
   - Checks if Docker Desktop is running and starts it if needed
   - Waits for Docker to initialize
   - Runs the start_monitoring.sh script using Git Bash

2. `setup_autostart.ps1` - A PowerShell script that:
   - Creates a Windows scheduled task to run the batch script at system startup
   - Configures the task to run with admin privileges
   - Adds a 2-minute delay after boot to ensure network connectivity

## Setup Instructions

### Option 1: Configure Docker Desktop and Scheduled Task Manually

1. **Configure Docker Desktop to start automatically:**
   - Open Docker Desktop
   - Go to Settings (gear icon)
   - Navigate to "General" settings
   - Check "Start Docker Desktop when you log in"
   - Click "Apply & Restart"

2. **Create a scheduled task manually:**
   - Open Task Scheduler (search for "Task Scheduler" in the Start menu)
   - Click "Create Task" in the right panel
   - Name: "HomeNetworkMonitor_Autostart"
   - Select "Run with highest privileges"
   - Go to the "Triggers" tab, click "New"
   - Begin the task: "At startup"
   - Add a delay: 2 minutes
   - Click OK
   - Go to the "Actions" tab, click "New"
   - Action: "Start a program"
   - Program/script: Browse to select the `scripts/autostart_monitoring.bat` file
   - Start in: Your project's root directory
   - Click OK, then OK again to create the task

### Option 2: Use the Automated Setup Script (Recommended)

1. **Right-click on `setup_autostart.ps1` and select "Run as administrator"**

   If you get a security warning, you may need to change the PowerShell execution policy:
   - Open PowerShell as administrator
   - Run: `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process`
   - Navigate to the script's directory
   - Run: `.\setup_autostart.ps1`

2. **Follow the prompts to create the scheduled task**

## Verifying the Setup

After setting up autostart:

1. Restart your computer
2. After 2-3 minutes, you should see:
   - Docker Desktop running in the system tray
   - The Home Network Monitor services running:
     - Check by opening a browser to http://localhost:3000 for Grafana
     - Check Docker Desktop to see the containers running

## Troubleshooting

If the services don't start automatically:

1. **Check if Docker Desktop is running**
   - If not, start it manually and wait a minute
   - Then try running the batch script manually

2. **Check the scheduled task status**
   - Open Task Scheduler
   - Find the "HomeNetworkMonitor_Autostart" task
   - Check the "Last Run Result" column
   - If there's an error, try running the task manually

3. **Check if Git Bash is installed**
   - The autostart script requires Git Bash to run the shell script
   - If not installed, get it from https://git-scm.com/download/win

## Disabling Autostart

To disable the automatic startup:

1. **Open Task Scheduler**
2. **Find the "HomeNetworkMonitor_Autostart" task**
3. **Either:**
   - Select it and click "Disable" in the right panel, or
   - Right-click and select "Delete" to remove it completely

4. **Optionally, disable Docker Desktop autostart:**
   - Open Docker Desktop settings
   - Uncheck "Start Docker Desktop when you log in"
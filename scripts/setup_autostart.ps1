# Home Network Monitor - Setup Autostart Task
# This script sets up a Windows scheduled task to run the monitoring services at system startup
# Must be run as Administrator

# Check if running as Administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "This script must be run as Administrator. Please re-run with elevated privileges." -ForegroundColor Red
    exit 1
}

# Get the full path to the project directory and batch file
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPath = Split-Path -Parent $scriptPath
$batchFilePath = Join-Path -Path $scriptPath -ChildPath "autostart_monitoring.bat"

# Verify the batch file exists
if (-not (Test-Path $batchFilePath)) {
    Write-Host "Error: Could not find $batchFilePath" -ForegroundColor Red
    Write-Host "Make sure you are running this script from the project directory." -ForegroundColor Red
    exit 1
}

Write-Host "================================================"
Write-Host "Home Network Monitor - Setup Autostart Task"
Write-Host "================================================"
Write-Host ""
Write-Host "This will set up a scheduled task to run the monitoring services at system startup."
Write-Host "Project directory: $projectPath"
Write-Host "Batch file: $batchFilePath"
Write-Host ""

# Ask for confirmation
$confirmation = Read-Host "Do you want to continue? (y/n)"
if ($confirmation -ne 'y') {
    Write-Host "Setup canceled."
    exit 0
}

# Create the scheduled task
$taskName = "HomeNetworkMonitor_Autostart"
$taskDescription = "Starts Docker Desktop and Home Network Monitor services at system startup"

Write-Host "Creating scheduled task '$taskName'..."

# Remove existing task if it exists
Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue | Unregister-ScheduledTask -Confirm:$false -ErrorAction SilentlyContinue

# Create the action that will run the batch file
$action = New-ScheduledTaskAction -Execute $batchFilePath -WorkingDirectory $projectPath

# Create a trigger for system startup with a 2-minute delay to ensure network is available
$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = "PT2M"  # 2-minute delay

# Set the principal (run with highest privileges)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Set the settings (don't stop if running for a long time, etc.)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

# Register the task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description $taskDescription -Force

Write-Host "Scheduled task created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "The monitoring services will now start automatically when your system boots up,"
Write-Host "with a 2-minute delay to ensure network connectivity is established."
Write-Host ""
Write-Host "You can view or modify this task in Task Scheduler (taskschd.msc)."
Write-Host "Look for the task named '$taskName' in the Task Scheduler Library."
Write-Host ""
Write-Host "To disable autostart, open Task Scheduler and delete or disable the task."
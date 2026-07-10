# Registers the De Waag nightly job chain with Windows Task Scheduler.
# Run once (as your own user, no admin needed):
#   powershell -ExecutionPolicy Bypass -File scripts\register-scheduler.ps1
# The chain runs every morning at 08:10 (after US close + overnight), and
# on missed schedules runs as soon as the machine wakes.

$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"

$action = New-ScheduledTaskAction -Execute $python -Argument "-m dewaag.jobs nightly" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At 08:10
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName "DeWaag Nightly" -Action $action -Trigger $trigger -Settings $settings -Force
Write-Host "Registered: 'DeWaag Nightly' daily at 08:10 (runs on wake if missed)."
Write-Host "Test it now with:  Start-ScheduledTask -TaskName 'DeWaag Nightly'"

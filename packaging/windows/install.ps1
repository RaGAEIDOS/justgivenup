# JustGivenUp! Guardian — Windows installer (Python build)
# Run as Administrator:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#
# What it does:
#   1. copies the app into %LOCALAPPDATA%\JustGivenUp\app
#   2. creates run.bat launchers
#   3. registers autostart (HKCU Run key — no admin needed)
#   4. (admin only) creates a scheduled task that starts the daemon with
#      highest privileges so the hosts/DNS layer is available, and
#      enables the browser policy folder the extension docs mention
#
# Requirements: python3 (python.org launcher provides `python` or `py`).
# For the DNS layer run this file as Administrator the first time.

$ErrorActionPreference = "Stop"

$Source = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Dest = "$env:LOCALAPPDATA\JustGivenUp\app"
$AppDir = Join-Path $Dest "justgivenup"

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

Write-Host ""
Write-Host "=== JustGivenUp! Guardian (v3.0.0) ===" -ForegroundColor Cyan
Write-Host "Source : $Source"
Write-Host "Install: $Dest"

# python?
$Python = $null
foreach ($c in @("python", "py", "python3")) {
    $p = Get-Command $c -ErrorAction SilentlyContinue
    if ($p) { $Python = $p.Source; break }
}
if (-not $Python) {
    Write-Host "Python 3 not found." -ForegroundColor Red
    Write-Host "Install it first and rerun:"
    Write-Host "  winget install Python.Python.3.12"
    pause; exit 1
}
Write-Host "Python : $Python"

New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item -Recurse -Force (Join-Path $Source "app\justgivenup\*") $AppDir
Copy-Item -Force "$Source\app\web\index.html" "$AppDir\web\"
Copy-Item -Force "$Source\app\web\style.css" "$AppDir\web\"
Copy-Item -Force "$Source\app\web\app.js" "$AppDir\web\"
Copy-Item -Force "$Source\app\web\*.png" "$AppDir\web\" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path "$AppDir\data" | Out-Null
Copy-Item -Force "$Source\data\blocklist_full.txt" "$AppDir\data\" -ErrorAction SilentlyContinue
Copy-Item -Force "$Source\data\blocklist_core.txt" "$AppDir\data\" -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force "$Source\extension" "$AppDir\extension"

# launchers (PYTHONPATH set to the install dir)
$batRun = Join-Path $Dest "run.bat"
Set-Content -Path $batRun -Encoding ASCII -Value @"
@echo off
set PYTHONPATH=$Dest
set JGU_STATE_DIR=$env:PROGRAMDATA\JustGivenUp
"$Python" -m justgivenup run
"@
$batDash = Join-Path $Dest "dashboard.bat"
Set-Content -Path $batDash -Encoding ASCII -Value "start http://127.0.0.1:8081`r`n"

# autostart via HKCU Run key
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $RunKey -Name "JustGivenUp" -Value "`"$batRun`""

# desktop + start menu shortcuts
$Desktop = [Environment]::GetFolderPath("Desktop")
$StartMenu = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null
$Wsh = New-Object -ComObject WScript.Shell
foreach ($pair in @(@("$Desktop\JustGivenUp.lnk", "http://127.0.0.1:8081"),
                    @("$StartMenu\JustGivenUp.lnk", "http://127.0.0.1:8081"))) {
    $sc = $Wsh.CreateShortcut($pair[0])
    $sc.TargetPath = "explorer.exe"
    $sc.Arguments = $pair[1]
    $sc.Save()
}

# elevated scheduled task (hosts layer) — admin only
if ($isAdmin) {
    $action = New-ScheduledTaskAction -Execute "$batRun"
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    Register-ScheduledTask -TaskName "JustGivenUp Guardian (elevated)" `
        -Action $action -Trigger $trigger `
        -User "$env:COMPUTERNAME\$env:USERNAME" `
        -RunLevel Highest -Force | Out-Null
    Write-Host "[admin] Scheduled task created (hosts layer will run elevated)."
} else {
    Write-Host "[notice] Not elevated: the daemon will host-block only after an admin run."
    Write-Host "         Re-run this script as Administrator once for the DNS layer."
}

Write-Host ""
Write-Host "OK: start the daemon with:  `"$batRun`"" -ForegroundColor Green
Write-Host "Dashboard: http://127.0.0.1:8081"
Write-Host ""
Write-Host "Browser extension (optional, recommended):"
Write-Host "  Chrome/Edge: chrome://extensions -> Load unpacked ->"
Write-Host "             $Dest\justgivenup\extension"
Write-Host "  Firefox:   about:addons -> Install Add-on From File ->"
Write-Host "             $Dest\justgivenup\extension\justgivenup.xpi"
Write-Host ""
pause

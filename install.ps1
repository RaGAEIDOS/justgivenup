# JustGivenUp! Installer
# Run as Administrator:  powershell -ExecutionPolicy Bypass -File install.ps1

$ErrorActionPreference = "Stop"
$Source = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Dest = "$env:ProgramFiles\JustGivenUp"

Write-Host "=== JustGivenUp! Installer ===" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Destination: $Dest"

# Require admin
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Please run as Administrator!" -ForegroundColor Red
    pause
    exit 1
}

# Stop any running instances
Write-Host "Stopping running instances..." -ForegroundColor Yellow
Get-Process "JustGivenUp*" -ErrorAction SilentlyContinue | Stop-Process -Force

# Create destination
if (Test-Path $Dest) {
    Remove-Item -Path "$Dest\*" -Recurse -Force
}
New-Item -ItemType Directory -Path $Dest -Force | Out-Null

# Copy all files from build directory
$BuildDir = "$Source\build"
if (-NOT (Test-Path $BuildDir)) {
    Write-Host "ERROR: build directory not found at $BuildDir" -ForegroundColor Red
    Write-Host "Run 'cmake --build build' first or download a release." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "Copying files..." -ForegroundColor Yellow
Get-ChildItem -Path $BuildDir -File | Copy-Item -Destination $Dest -Force

# Copy model and config
if (Test-Path "$BuildDir\320n.onnx") {
    Copy-Item "$BuildDir\320n.onnx" "$Dest\" -Force
}

# Install auto-start (Registry Run key)
Write-Host "Installing auto-start..." -ForegroundColor Yellow
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$ExePath = "$Dest\JustGivenUp.exe"
Set-ItemProperty -Path $RunKey -Name "JustGivenUp" -Value $ExePath

# Create Start Menu shortcut
Write-Host "Creating Start Menu shortcut..." -ForegroundColor Yellow
$WshShell = New-Object -ComObject WScript.Shell
$StartMenu = [Environment]::GetFolderPath("Programs")
$Shortcut = $WshShell.CreateShortcut("$StartMenu\JustGivenUp.lnk")
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = $Dest
$Shortcut.Description = "JustGivenUp! Screen Guardian"
$Shortcut.Save()

# Create desktop shortcut
$Desktop = [Environment]::GetFolderPath("Desktop")
$Shortcut = $WshShell.CreateShortcut("$Desktop\JustGivenUp.lnk")
$Shortcut.TargetPath = $ExePath
$Shortcut.WorkingDirectory = $Dest
$Shortcut.Description = "JustGivenUp! Screen Guardian"
$Shortcut.Save()

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Green
Write-Host "Installed to: $Dest"
Write-Host ""
Write-Host "To lock the program for 30 days, run:" -ForegroundColor Cyan
Write-Host "  $Dest\JustGivenUp.exe --lock--30" -ForegroundColor White
Write-Host ""
Write-Host "To start normally (system tray):" -ForegroundColor Cyan
Write-Host "  $Dest\JustGivenUp.exe" -ForegroundColor White
pause

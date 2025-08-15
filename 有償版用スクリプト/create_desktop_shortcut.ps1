# DaVinci Resolve Auto Editor - Desktop Shortcut Creator (PowerShell)
# =======================================================================

Write-Host ""
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "       DaVinci Resolve Auto Editor Shortcut Creator" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory and PowerShell script path
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PowerShellScript = Join-Path $ScriptDir "run_auto_video_editor.ps1"

# Check if PowerShell script exists
if (-not (Test-Path $PowerShellScript)) {
    Write-Host "[ERROR] run_auto_video_editor.ps1 not found." -ForegroundColor Red
    Write-Host "Please ensure the file exists in this directory." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Get desktop path
try {
    $DesktopPath = [Environment]::GetFolderPath("Desktop")
    if (-not $DesktopPath -or -not (Test-Path $DesktopPath)) {
        throw "Desktop path not found"
    }
    Write-Host "[INFO] Desktop path: $DesktopPath" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Could not get desktop path: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[INFO] Script path: $ScriptDir" -ForegroundColor Green
Write-Host ""

# Create shortcut
try {
    $WshShell = New-Object -comObject WScript.Shell
    $ShortcutPath = Join-Path $DesktopPath "DaVinci Resolve Auto Editor.lnk"
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    
    # Set shortcut properties to run PowerShell script
    $Shortcut.TargetPath = "powershell.exe"
    $Shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$PowerShellScript`""
    $Shortcut.WorkingDirectory = $ScriptDir
    $Shortcut.Description = "DaVinci Resolve Auto Video Editor Script (Paid Version)"
    $Shortcut.IconLocation = "powershell.exe,0"
    
    # Save shortcut
    $Shortcut.Save()
    
    Write-Host "[SUCCESS] Desktop shortcut created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Shortcut name: 'DaVinci Resolve Auto Editor.lnk'" -ForegroundColor Cyan
    Write-Host "Location: $DesktopPath" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "You can now double-click this shortcut to run the" -ForegroundColor Green
    Write-Host "auto video editor script from anywhere." -ForegroundColor Green
    
} catch {
    Write-Host "[ERROR] Failed to create shortcut: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Read-Host "Press Enter to close"
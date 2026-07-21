# DaVinci Resolve Auto Editor - Desktop Shortcut Creator (PowerShell)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launchers = @(
    @{
        File = "run_auto_video_editor.ps1"
        Name = "DaVinci Resolve Auto Editor - Stable.lnk"
        Description = "Stable: silence removal and Resolve template timeline"
    },
    @{
        File = "run_advanced_auto_video_editor.ps1"
        Name = "DaVinci Resolve Auto Editor - Advanced.lnk"
        Description = "Advanced: experimental highlight-first video editing"
    }
)

Write-Host ""
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "       DaVinci Resolve Auto Editor Shortcuts" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""

try {
    $DesktopPath = [Environment]::GetFolderPath("Desktop")
    if (-not $DesktopPath -or -not (Test-Path $DesktopPath)) {
        throw "Desktop path not found"
    }

    $WshShell = New-Object -ComObject WScript.Shell
    foreach ($Launcher in $Launchers) {
        $PowerShellScript = Join-Path $ScriptDir $Launcher.File
        if (-not (Test-Path $PowerShellScript)) {
            throw "Launcher not found: $PowerShellScript"
        }

        $ShortcutPath = Join-Path $DesktopPath $Launcher.Name
        $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = "powershell.exe"
        $Shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$PowerShellScript`""
        $Shortcut.WorkingDirectory = $ScriptDir
        $Shortcut.Description = $Launcher.Description
        $Shortcut.IconLocation = "powershell.exe,0"
        $Shortcut.Save()

        Write-Host "[CREATED] $($Launcher.Name)" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Use Stable when the recording only needs the proven cut and template." -ForegroundColor Cyan
    Write-Host "Use Advanced when you want to try the latest editing features." -ForegroundColor Cyan
}
catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Read-Host "Press Enter to close"

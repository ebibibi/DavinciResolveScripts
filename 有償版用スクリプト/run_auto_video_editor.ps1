# Stable DaVinci Resolve auto editor runner
# This is the proven workflow: silence removal + template timeline creation.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$RequiredCommands = @("python", "auto-editor")
foreach ($Command in $RequiredCommands) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "Required command was not found: $Command"
    }
}

Write-Host "Starting stable editing..." -ForegroundColor Cyan
Write-Host "Workflow: auto-editor silence removal + Resolve template timeline"
& python "auto_video_editor.py"
if ($LASTEXITCODE -ne 0) {
    throw "Stable editing failed with exit code $LASTEXITCODE"
}

Write-Host "Done. Review the generated timeline in DaVinci Resolve." -ForegroundColor Green
Read-Host "Press Enter to close"

# Dual source video editor runner (slides on V1, camera on V2)
# The recording folder holds one .mkv screen capture and one .mp4 camera file.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$RequiredCommands = @("python", "auto-editor", "ffmpeg")
foreach ($Command in $RequiredCommands) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "Required command was not found: $Command"
    }
}

$Arguments = @("dual_source_video_editor.py")
$Arguments += $args

Write-Host "Starting dual source editing..." -ForegroundColor Cyan
Write-Host "Workflow: audio sync + silence removal on both tracks + camera placement"
& python @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "Dual source editing failed with exit code $LASTEXITCODE"
}

Write-Host "Done. Apply Smooth Cut and the green screen key in Resolve." -ForegroundColor Green
Read-Host "Press Enter to close"

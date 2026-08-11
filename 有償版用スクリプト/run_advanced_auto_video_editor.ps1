# Advanced highlight-first video editor runner
# Experimental features live here and do not change the stable Resolve workflow.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$RequiredCommands = @("python", "auto-editor", "ffmpeg", "ffprobe")
foreach ($Command in $RequiredCommands) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "Required command was not found: $Command"
    }
}

$Arguments = @("highlight_video.py")
$LocalConfig = Join-Path $ScriptDir "config.local.json"
$LegacyConfig = Join-Path $ScriptDir "config.json"
if (Test-Path $LocalConfig) {
    $Arguments += @("--config", $LocalConfig)
}
elseif (Test-Path $LegacyConfig) {
    $Arguments += @("--config", $LegacyConfig)
}

Write-Host "Starting advanced highlight-first editing..." -ForegroundColor Cyan
Write-Host "Workflow: silence removal + opening highlights + takeaway title"
& python @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "Advanced editing failed with exit code $LASTEXITCODE"
}

Write-Host "Done. The final MP4 and highlight_plan.json are in _highlight_output." -ForegroundColor Green
Read-Host "Press Enter to close"

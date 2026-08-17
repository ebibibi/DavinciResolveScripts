# Stable DaVinci Resolve auto editor runner
# This is the proven workflow: silence removal + template timeline creation.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# マージされた修正が編集機に届いていない事故を止めるため、実行のたびに最新版へ
# 揃える。更新できなくても止めず、どの版で走っているかを必ず表示する。
. (Join-Path $ScriptDir "update_repository.ps1")
Update-Repository -RepositoryRoot (Split-Path -Parent $ScriptDir) | Out-Null

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

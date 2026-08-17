# Dual source video editor runner (slides on V1, camera on V2)
# The recording folder holds one .mkv screen capture and one .mp4 camera file.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# マージされた修正が編集機に届いていない事故を止めるため、実行のたびに最新版へ
# 揃える。更新できなくても止めず、どの版で走っているかを必ず表示する。
. (Join-Path $ScriptDir "update_repository.ps1")
Update-Repository -RepositoryRoot (Split-Path -Parent $ScriptDir) | Out-Null

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

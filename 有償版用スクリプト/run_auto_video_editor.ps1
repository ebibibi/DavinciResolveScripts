# DaVinci Resolve Auto Video Editor Script Runner (PowerShell)
# ============================================================

# Set console encoding for Japanese characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Get script directory and change to it
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Execute Python script
python "auto_video_editor.py"

# Pause to keep window open
Read-Host "Press Enter to close"
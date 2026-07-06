# DaVinci Resolve Auto Video Editor Script Runner (PowerShell)
# ============================================================

# Set console encoding for Japanese characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Get script directory and change to it
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Test-CommandAvailable {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-PythonModule {
    param([string]$ModuleName)
    python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$ModuleName') else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

function Update-CurrentPath {
    $MachinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $UserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$MachinePath;$UserPath"
}

function Install-AiAssistToolsIfRequested {
    $MissingTools = @()
    $MissingPipPackages = @()

    $WhisperAvailable = (Test-CommandAvailable "whisper") -or (Test-PythonModule "whisper")
    if (-not $WhisperAvailable) {
        $MissingTools += "whisper"
        $MissingPipPackages += "openai-whisper"
    }

    if (-not (Test-PythonModule "PIL")) {
        $MissingTools += "Pillow"
        $MissingPipPackages += "Pillow"
    }

    if (-not (Test-CommandAvailable "ffmpeg")) {
        $MissingTools += "ffmpeg"
    }

    if ($MissingTools.Count -eq 0) {
        return
    }

    Write-Host ""
    Write-Host "Optional AI assist tools are missing: $($MissingTools -join ', ')" -ForegroundColor Yellow
    Write-Host "Press Y to install them now. Press Enter to skip and continue normal editing."
    $Answer = Read-Host "Install AI assist tools? [Y/Enter]"
    if ($Answer -notmatch "^[Yy]$") {
        Write-Host "Skipping AI assist tool installation."
        return
    }

    if ($MissingPipPackages.Count -gt 0) {
        Write-Host "Installing Python packages: $($MissingPipPackages -join ', ')"
        & python -m pip install --upgrade @MissingPipPackages
    }

    if (-not (Test-CommandAvailable "ffmpeg")) {
        if (Test-CommandAvailable "winget") {
            Write-Host "Installing ffmpeg with winget..."
            & winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
            Update-CurrentPath
        } else {
            Write-Host "winget was not found. Install ffmpeg manually to enable hook card videos." -ForegroundColor Yellow
        }
    }
}

Install-AiAssistToolsIfRequested

# Execute Python script
python "auto_video_editor.py"

# Pause to keep window open
Read-Host "Press Enter to close"

# DaVinci Resolve Auto Video Editor Script Runner (PowerShell)
# ============================================================

# Set console encoding for Japanese characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Get script directory and change to it
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
$RepoRoot = Split-Path -Parent $ScriptDir

function Test-CommandAvailable {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-PythonModule {
    param([string]$ModuleName)
    python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$ModuleName') else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

function Test-TorchCudaAvailable {
    python -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

function Update-CurrentPath {
    $MachinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $UserPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$MachinePath;$UserPath"
}

function Update-RepositoryBeforeRun {
    if (-not (Test-CommandAvailable "git")) {
        Write-Host "git was not found. Install git or run from a cloned repository." -ForegroundColor Red
        exit 1
    }

    if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
        Write-Host "Git repository was not found at $RepoRoot. Cannot run git pull." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "Updating DavinciResolveScripts with git pull --ff-only --autostash..." -ForegroundColor Cyan
    Push-Location $RepoRoot
    try {
        & git pull --ff-only --autostash
        if ($LASTEXITCODE -ne 0) {
            Write-Host "git pull failed. Resolve the repository state before running the editor." -ForegroundColor Red
            exit $LASTEXITCODE
        }
    } finally {
        Pop-Location
        Set-Location $ScriptDir
    }

    $env:DAVINCI_GIT_PULL_DONE = "1"
}

function Install-AiAssistToolsIfRequested {
    $MissingTools = @()
    $MissingPipPackages = @()
    $InstallCudaTorch = $false

    $WhisperAvailable = (Test-CommandAvailable "whisper") -or (Test-PythonModule "whisper")
    if (-not $WhisperAvailable) {
        $MissingTools += "whisper"
        $MissingPipPackages += "openai-whisper"
    }

    if (-not (Test-CommandAvailable "ffmpeg")) {
        $MissingTools += "ffmpeg"
    }

    if ((Test-CommandAvailable "nvidia-smi") -and -not (Test-TorchCudaAvailable)) {
        $MissingTools += "PyTorch CUDA"
        $InstallCudaTorch = $true
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

    if ($InstallCudaTorch) {
        $TorchCudaIndexUrl = $env:DAVINCI_TORCH_CUDA_INDEX_URL
        if ([string]::IsNullOrWhiteSpace($TorchCudaIndexUrl)) {
            $TorchCudaIndexUrl = "https://download.pytorch.org/whl/cu126"
        }
        Write-Host "Installing CUDA-enabled PyTorch from $TorchCudaIndexUrl ..."
        & python -m pip install --upgrade torch torchvision torchaudio --index-url $TorchCudaIndexUrl
    }

    if (-not (Test-CommandAvailable "ffmpeg")) {
        if (Test-CommandAvailable "winget") {
            Write-Host "Installing ffmpeg with winget..."
            & winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
            Update-CurrentPath
        } else {
            Write-Host "winget was not found. Install ffmpeg manually if Whisper audio extraction requires it." -ForegroundColor Yellow
        }
    }
}

Update-RepositoryBeforeRun
Install-AiAssistToolsIfRequested

# Execute Python script
python "auto_video_editor.py"

# Pause to keep window open
Read-Host "Press Enter to close"

# Install the bundled titles without starting an editing job.
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "update_repository.ps1")
Update-Repository -RepositoryRoot (Split-Path -Parent $ScriptDir) | Out-Null
& python (Join-Path $ScriptDir "install_title_presets.py") @args
if ($LASTEXITCODE -ne 0) { throw "Title installation failed: $LASTEXITCODE" }

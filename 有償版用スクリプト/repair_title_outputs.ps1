# Repair disconnected EBI titles in the currently open timeline.
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptDir "update_repository.ps1")
Update-Repository -RepositoryRoot (Split-Path -Parent $ScriptDir) | Out-Null
& python (Join-Path $ScriptDir "repair_title_outputs.py") @args
if ($LASTEXITCODE -ne 0) { throw "Title repair failed: $LASTEXITCODE" }

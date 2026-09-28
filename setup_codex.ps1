# Compatibility entry point. Prefer double-clicking INSTALL.cmd on Windows.
# This script does not change execution policy or configure the old agent team.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& (Join-Path $PSScriptRoot 'INSTALL.cmd')
exit $LASTEXITCODE

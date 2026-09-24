# Run from a PowerShell session on the Windows computer that runs CATIA V5.
# No Git, administrator rights, or global Python packages are required.
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $projectRoot '.venv')
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv (Join-Path $projectRoot '.venv')
    } else {
        throw 'Python 3.10+ was not found. Install or locate the approved Windows Python first.'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the local virtual environment.' }
}

& $venvPython -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'The local .venv must use Python 3.10 or newer.' }

& $venvPython -m pip install -e $projectRoot
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

& $venvPython (Join-Path $projectRoot 'test_server.py')
if ($LASTEXITCODE -ne 0) { throw 'Offline server registration test failed.' }

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw 'Codex CLI was not found in PATH. Install the approved Codex CLI, then rerun this script.'
}

function Get-CatiaMcpEntry {
    param([string]$Name)
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $existingJson = & codex mcp get $Name --json 2>$null
        $getExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($getExitCode -ne 0) { return $null }
    $existing = ($existingJson -join "`n") | ConvertFrom-Json
    $entry = $existing
    if ($existing.config) { $entry = $existing.config }
    $enabled = ($existing.enabled -ne $false) -and ($entry.enabled -ne $false)
    if ($entry.transport) {
        $entry = $entry.transport
        if ($entry.stdio) { $entry = $entry.stdio }
    }
    return [PSCustomObject]@{
        command = $entry.command
        args = $entry.args
        enabled = $enabled -and ($entry.enabled -ne $false)
    }
}

function Assert-CatiaMcpEntry {
    param($Entry, [string]$Name, [string[]]$ExpectedArguments)
    $sameCommand = [string]::Equals(
        [string]$Entry.command, $venvPython,
        [System.StringComparison]::OrdinalIgnoreCase
    )
    $actualArguments = @($Entry.args)
    $sameArgs = $actualArguments.Count -eq $ExpectedArguments.Count
    if ($sameArgs) {
        for ($index = 0; $index -lt $ExpectedArguments.Count; $index++) {
            if ($actualArguments[$index] -ne $ExpectedArguments[$index]) {
                $sameArgs = $false
            }
        }
    }
    if (-not ($sameCommand -and $sameArgs)) {
        throw "Codex has a different $Name MCP entry. Inspect it with codex mcp get $Name --json. It will not be overwritten."
    }
}

# Inspect the user configuration outside project config layers. No project
# config.toml is generated or modified here.
Push-Location -LiteralPath ([System.IO.Path]::GetTempPath())
try {
    & codex mcp list
    if ($LASTEXITCODE -ne 0) { throw 'Could not read Codex MCP configuration.' }
    $inspectionEntry = Get-CatiaMcpEntry 'catia-v5-inspect'
    $legacyWriterEntry = Get-CatiaMcpEntry 'catia-v5'
    if ($null -ne $inspectionEntry) {
        Assert-CatiaMcpEntry $inspectionEntry 'catia-v5-inspect' @('-m', 'catia_mcp', '--inspection-only')
        if (-not $inspectionEntry.enabled) {
            throw 'The matching catia-v5-inspect entry is disabled. Enable it in your Codex user configuration, then rerun setup. No configuration was replaced.'
        }
    }
    if ($null -ne $legacyWriterEntry) {
        Assert-CatiaMcpEntry $legacyWriterEntry 'catia-v5' @('-m', 'catia_mcp')
    }

    & $venvPython (Join-Path $projectRoot 'scripts\configure_codex_agents.py')
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure the Codex agent roles.' }

    if ($null -eq $inspectionEntry) {
        & codex mcp add catia-v5-inspect -- $venvPython -m catia_mcp --inspection-only
        if ($LASTEXITCODE -ne 0) { throw 'Inspection MCP registration failed.' }
    }
    if ($null -ne $legacyWriterEntry) {
        # Migrate only this project's matching old registration. The full server
        # is now configured inside cad_executor.toml instead of the main chat.
        & codex mcp remove catia-v5
        if ($LASTEXITCODE -ne 0) { throw 'Could not migrate the old writer registration.' }
        Write-Host 'Moved this project''s full catia-v5 access into the executor role.'
    }
    & codex mcp get catia-v5-inspect --json
    if ($LASTEXITCODE -ne 0) { throw 'Inspection MCP registration check failed.' }
} finally {
    Pop-Location
}
Write-Host 'Setup complete. Restart Codex in this project and trust its local configuration.'
Write-Host 'The coordinator inspects CATIA; cad_executor alone has the full MCP tool set.'

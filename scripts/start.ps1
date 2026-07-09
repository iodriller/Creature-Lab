param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"
$ScriptPath = Join-Path $PSScriptRoot "start.py"

function Test-PythonCandidate {
    param(
        [string]$Executable,
        [string[]]$PrefixArgs
    )

    $Command = Get-Command $Executable -ErrorAction SilentlyContinue
    if (-not $Command) {
        return $null
    }

    & $Command.Source @PrefixArgs -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" *> $null
    if ($LASTEXITCODE -eq 0) {
        return @{
            Source = $Command.Source
            PrefixArgs = $PrefixArgs
        }
    }

    return $null
}

$Python = Test-PythonCandidate -Executable "py" -PrefixArgs @("-3")
if (-not $Python) {
    $Python = Test-PythonCandidate -Executable "python" -PrefixArgs @()
}
if (-not $Python) {
    $Python = Test-PythonCandidate -Executable "python3" -PrefixArgs @()
}

if (-not $Python) {
    Write-Host "Creature Lab needs Python 3.11 or newer." -ForegroundColor Red
    Write-Host "Install Python from https://www.python.org/downloads/ and rerun:"
    Write-Host "  .\scripts\start.ps1"
    exit 1
}

& $Python.Source @($Python.PrefixArgs) $ScriptPath @RemainingArgs
exit $LASTEXITCODE

param(
  [ValidateSet("run", "doctor", "repair", "docker", "stop", "logs")]
  [string]$Action = "run",
  [switch]$NoBrowser,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$UvVersion = "0.12.5"

function Invoke-Retry([string]$Label, [scriptblock]$Operation) {
  for ($attempt = 1; $attempt -le 3; $attempt++) {
    try { & $Operation; return } catch {
      if ($attempt -eq 3) { throw "$Label failed after 3 attempts: $($_.Exception.Message)" }
      Start-Sleep -Seconds ([math]::Pow(2, $attempt - 1))
    }
  }
}

function Resolve-Uv {
  $command = Get-Command uv -ErrorAction SilentlyContinue
  foreach ($candidate in @($(if ($command) { $command.Source }), "$env:USERPROFILE\.local\bin\uv.exe", "$env:USERPROFILE\.cargo\bin\uv.exe")) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
  }
  return $null
}

function Ensure-Uv {
  $uv = Resolve-Uv
  if ($uv) { return $uv }
  $installer = Join-Path $env:TEMP "creature-lab-uv-$UvVersion.ps1"
  try {
    Invoke-Retry "uv download" { Invoke-WebRequest -UseBasicParsing -Uri "https://astral.sh/uv/$UvVersion/install.ps1" -OutFile $installer }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
  } finally { Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue }
  $uv = Resolve-Uv
  if (-not $uv) { throw "uv installed but could not be located." }
  return $uv
}

function Wait-Ready {
  for ($i = 0; $i -lt 120; $i++) {
    try { $client = [Net.Sockets.TcpClient]::new("127.0.0.1", 8080); $client.Dispose(); return $true }
    catch { Start-Sleep -Milliseconds 500 }
  }
  return $false
}

if ($Action -in @("docker", "stop", "logs")) {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  $engineRunning = $false
  if ($docker) { docker info *> $null; $engineRunning = ($LASTEXITCODE -eq 0) }
  if ($Action -eq "stop" -and -not $engineRunning) { Write-Host "The native server runs in the foreground. Press Ctrl+C in its terminal to stop it."; exit 0 }
  if ($Action -eq "logs" -and -not $engineRunning) { Write-Host "The native server writes logs to its foreground terminal."; exit 0 }
  if (-not $docker) { throw "Docker is not installed." }
  if (-not $engineRunning) { throw "Docker is installed but its engine is not running." }
  if ($Action -eq "stop") { docker compose down; exit $LASTEXITCODE }
  if ($Action -eq "logs") { docker compose logs --follow; exit $LASTEXITCODE }
  docker compose up --detach --build
  if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed to start Creature Lab." }
  if (-not (Wait-Ready)) { docker compose logs; throw "Creature Lab did not become ready." }
  Write-Host "Creature Lab is ready at http://127.0.0.1:8080" -ForegroundColor Green
  if (-not $NoBrowser) { Start-Process "http://127.0.0.1:8080" }
  exit 0
}

$uv = if ($Action -eq "doctor") { Resolve-Uv } else { Ensure-Uv }
if (-not $uv) { throw "uv is missing. Run .\run.ps1 once to install the managed runtime." }

if ($Action -eq "doctor") {
  & $uv run --frozen --no-sync creature-lab doctor
  exit $LASTEXITCODE
}

if ($Action -eq "repair") {
  Invoke-Retry "dependency repair" { & $uv sync --frozen --reinstall --extra sim --extra viz; if ($LASTEXITCODE -ne 0) { throw "uv sync exited with $LASTEXITCODE" } }
}

$launchArgs = @("run", "--python", "3.11", "--frozen", "python", "scripts/start.py")
if ($NoBrowser) { $launchArgs += "--no-open-browser" }
$launchArgs += $RemainingArgs
& $uv @launchArgs
exit $LASTEXITCODE

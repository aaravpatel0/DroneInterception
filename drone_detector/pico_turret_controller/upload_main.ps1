param(
    [string]$Port = "auto"
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

python -m pip show mpremote *> $null
if ($LASTEXITCODE -ne 0) {
    python -m pip install mpremote
}

if ($Port -eq "auto") {
    python -m mpremote fs cp main.py :main.py
} else {
    python -m mpremote connect $Port fs cp main.py :main.py
}

Write-Host "Uploaded Pico turret main.py. Press reset or unplug/replug the Pico."

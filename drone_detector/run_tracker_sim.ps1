param(
    [string]$Source = "0",
    [string]$Port = "",
    [double]$KpPan = 0.50,
    [double]$KpTilt = 0.15
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
}

$trackerArgs = @(
    "live_tracker\run_tracker_with_simulator.py",
    "--",
    "--source", $Source,
    "--show",
    "--kp-pan", "$KpPan",
    "--max-pan-step", "85",
    "--min-pan-step", "12",
    "--deadband-x", "18",
    "--kp-tilt", "$KpTilt",
    "--y-deadband-inches", "1",
    "--command-interval", "0",
    "--tilt-min", "80",
    "--tilt-max", "130",
    "--tilt-start", "85",
    "--prediction-horizon-sec", "0.18",
    "--max-prediction-step-inches", "14",
    "--prediction-alpha", "0.55",
    "--velocity-alpha", "0.30",
    "--lost-target-hold-sec", "0.15",
    "--tracking-log", "live_tracker\tracking_log.csv",
    "--imgsz", "256",
    "--console-log-interval", "0.1"
)

if ($Port.Trim()) {
    $trackerArgs += @("--port", $Port)
}

python @trackerArgs

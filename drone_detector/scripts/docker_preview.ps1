Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
docker compose run --rm cpu python preview_labels.py --split train --count 20
docker compose run --rm cpu python preview_labels.py --split val --count 20
docker compose run --rm cpu python preview_labels.py --split test --count 20

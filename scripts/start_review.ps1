param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    if (-not (Test-Path 'review-ui/dist/index.html')) {
        & npm.cmd install --prefix review-ui
        if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
        & npm.cmd run build --prefix review-ui
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    }
    if (-not (Test-Path 'review_data/snapshot.json')) {
        & python scripts/review_server.py --import-snapshot logs/merge_experiments_snapshot.json --port $Port
    } else {
        & python scripts/review_server.py --port $Port
    }
} finally { Pop-Location }

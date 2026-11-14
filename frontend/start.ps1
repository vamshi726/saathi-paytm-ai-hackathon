# Run from any directory: powershell -ExecutionPolicy Bypass -File frontend/start.ps1
$ErrorActionPreference = 'Stop'
$originalPath = $env:PATH
try {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        $runtimeRoot = Join-Path (Split-Path $PSScriptRoot -Parent) '.runtime'
        $portableNode = Get-ChildItem -LiteralPath $runtimeRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like 'node-v*-win-x64' -and (Test-Path -LiteralPath (Join-Path $_.FullName 'node.exe')) } |
            Sort-Object Name -Descending | Select-Object -First 1
        if (-not $portableNode) { throw 'Install Node.js 22.12+ and run npm ci inside frontend first.' }
        $env:PATH = $portableNode.FullName + ';' + $env:PATH
    }
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'node_modules'))) {
        throw 'Dependencies are missing. Run npm ci inside frontend first.'
    }
    & npm.cmd --prefix $PSScriptRoot run dev
    exit $LASTEXITCODE
} finally {
    $env:PATH = $originalPath
}

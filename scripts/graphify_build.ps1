# graphify_build.ps1 - turn corpus/ into a provenance-tagged graph
#
#   pip install graphifyy
#   python scripts/graphify_build.ps1
#
# graphify reads the markdown / PDF in corpus/ with an LLM and writes a graph of
# nodes and links, tagging every link EXTRACTED | INFERRED | AMBIGUOUS. The
# SchemeSetu backend imports that file on startup (GRAPHIFY_AUTO_IMPORT=1) and
# merges it into the curated scheme graph, so the UI can show document-level
# evidence next to each rule.
#
# Keys: graphify is OpenAI-compatible and reads OPENAI_*. To reuse the
# OpenRouter key from .env instead of buying an OpenAI key:
#   $env:OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
#   $env:OPENAI_API_KEY  = "<your OPENROUTER_API_KEY>"
#   $env:OPENAI_MODEL    = "meta-llama/llama-3.3-70b-instruct"

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$corpus = Join-Path $root "corpus"
$outDir = Join-Path $root "graphify-out"
$outFile = Join-Path $outDir "graph.json"

Write-Host "SchemeSetu :: graphify extraction" -ForegroundColor Cyan
Write-Host "  corpus : $corpus"
Write-Host "  output : $outFile"

if (-not (Test-Path $corpus)) { throw "corpus/ not found - create it and add scheme documents." }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# Load .env into the process environment (so keys are available without a shell profile).
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
            $name = $Matches[1]
            $value = $Matches[2].Trim()
            if ($value -ne "" -and -not $env:$name) { Set-Item -Path "env:$name" -Value $value }
        }
    }
}

$graphify = Get-Command graphify -ErrorAction SilentlyContinue
if (-not $graphify) {
    Write-Host ""
    Write-Host "graphify is not installed (this is expected on a fresh machine)." -ForegroundColor Yellow
    Write-Host "Install it with:" -ForegroundColor Yellow
    Write-Host "  pip install graphifyy"
    Write-Host ""
    Write-Host "The app runs fine without it: data/schemes.json is already curated and"
    Write-Host "every scheme carries its own source_url / verified_on / provenance tag."
    Write-Host "Once graphify-out/graph.json exists, /api/health will report the merged"
    Write-Host "node and edge counts and the graph view will show document evidence."
    exit 0
}

if (-not $env:OPENAI_API_KEY -and -not $env:ANTHROPIC_API_KEY -and -not $env:GEMINI_API_KEY) {
    Write-Host "No LLM key found for graphify. Set OPENAI_API_KEY (or point OPENAI_BASE_URL" -ForegroundColor Yellow
    Write-Host "at OpenRouter and reuse OPENROUTER_API_KEY), then run this script again." -ForegroundColor Yellow
    exit 0
}

Write-Host "Running graphify extract ..." -ForegroundColor Green
# graphify's CLI has stayed stable across versions; --out is honoured, and the
# tool writes graph.json into the target directory when --out is omitted.
graphify extract $corpus --out $outFile

if (Test-Path $outFile) {
    $json = Get-Content $outFile -Raw | ConvertFrom-Json
    $nodes = if ($json.nodes) { $json.nodes.Count } else { 0 }
    $links = if ($json.links) { $json.links.Count } else { 0 }
    Write-Host ("Done: {0} nodes, {1} links -> {2}" -f $nodes, $links, $outFile) -ForegroundColor Green
    Write-Host "Restart the app (or press the reload button) to merge it into the graph."
} else {
    Write-Host "graphify finished but no graph.json was written - check the tool output above." -ForegroundColor Yellow
}
